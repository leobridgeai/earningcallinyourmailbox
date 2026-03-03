"""Financial Modeling Prep API client for earnings calendar and transcripts."""

import json
import logging
import urllib.request
import urllib.error
from datetime import date

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
    """Build a list of recent quarter candidates to check for each watchlist symbol.

    Instead of using the paid earning_calendar endpoint, we calculate the
    current and previous quarter and try fetching transcripts directly.
    Returns list of dicts with keys: symbol, quarter, year.
    """
    today = date.today()
    candidates = _recent_quarters(today, count=2)

    results = []
    for symbol in watchlist:
        for quarter, year in candidates:
            results.append({
                "symbol": symbol.upper(),
                "date": today.isoformat(),
                "quarter": quarter,
                "year": year,
            })

    logger.info("Will check %d symbol/quarter combinations", len(results))
    return results


def _recent_quarters(ref_date: date, count: int = 2) -> list[tuple[int, int]]:
    """Return the most recent `count` fiscal quarters as (quarter, year) tuples."""
    month = ref_date.month
    current_q = (month - 1) // 3 + 1
    year = ref_date.year

    quarters = []
    q, y = current_q, year
    for _ in range(count):
        quarters.append((q, y))
        q -= 1
        if q == 0:
            q = 4
            y -= 1
    return quarters



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
