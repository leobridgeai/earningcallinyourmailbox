"""Financial Modeling Prep API client for earnings calendar and transcripts."""

import json
import logging
import urllib.request
import urllib.error
from datetime import date, timedelta

logger = logging.getLogger(__name__)

BASE_URL = "https://financialmodelingprep.com/api/v3"


def _api_get(endpoint: str, params: dict) -> list | dict | None:
    """Make a GET request to the FMP API. Returns parsed JSON or None on error."""
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}/{endpoint}?{query}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EarningsCallAgent/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            # FMP returns {"Error Message": "..."} on some errors
            if isinstance(data, dict) and "Error Message" in data:
                logger.error("FMP API error: %s", data["Error Message"])
                return None
            return data
    except urllib.error.HTTPError as e:
        logger.error("FMP HTTP error %d for %s: %s", e.code, endpoint, e.reason)
        return None
    except (urllib.error.URLError, TimeoutError) as e:
        logger.error("FMP request failed for %s: %s", endpoint, e)
        return None


def get_recent_earnings(api_key: str, watchlist: list[str], days_back: int = 7) -> list[dict]:
    """Fetch recent earnings events for watchlist symbols.

    Returns list of dicts with keys: symbol, date, quarter, year.
    Only includes symbols from the watchlist.
    """
    today = date.today()
    start = today - timedelta(days=days_back)

    data = _api_get("earning_calendar", {
        "from": start.isoformat(),
        "to": today.isoformat(),
        "apikey": api_key,
    })

    if not data:
        return []

    watchlist_upper = {s.upper() for s in watchlist}
    results = []

    for entry in data:
        symbol = entry.get("symbol", "").upper()
        if symbol not in watchlist_upper:
            continue

        earning_date = entry.get("date", "")
        # Determine fiscal quarter and year from the date
        fiscal_year = entry.get("fiscalDateEnding", earning_date)[:4] if entry.get("fiscalDateEnding") else earning_date[:4]

        # FMP earnings calendar includes quarter info in some responses
        # We'll derive quarter from the fiscal date ending month
        quarter = _estimate_quarter(entry.get("fiscalDateEnding", earning_date))

        if fiscal_year and quarter:
            results.append({
                "symbol": symbol,
                "date": earning_date,
                "quarter": quarter,
                "year": int(fiscal_year),
            })

    logger.info("Found %d earnings events for watchlist (last %d days)", len(results), days_back)
    return results


def _estimate_quarter(date_str: str) -> int | None:
    """Estimate fiscal quarter from a date string (YYYY-MM-DD)."""
    if not date_str or len(date_str) < 7:
        return None
    try:
        month = int(date_str[5:7])
    except ValueError:
        return None
    # Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec
    return (month - 1) // 3 + 1


def get_transcript(api_key: str, symbol: str, quarter: int, year: int) -> str | None:
    """Fetch an earnings call transcript for a specific symbol, quarter, and year.

    Returns the transcript text or None if unavailable.
    """
    data = _api_get(f"earning_call_transcript/{symbol}", {
        "quarter": quarter,
        "year": year,
        "apikey": api_key,
    })

    if not data:
        logger.warning("No transcript data for %s Q%d %d", symbol, quarter, year)
        return None

    # FMP returns a list with one entry containing the transcript
    if isinstance(data, list) and len(data) > 0:
        content = data[0].get("content", "")
        if content:
            logger.info("Fetched transcript for %s Q%d %d (%d chars)", symbol, quarter, year, len(content))
            return content

    logger.warning("Empty transcript for %s Q%d %d", symbol, quarter, year)
    return None
