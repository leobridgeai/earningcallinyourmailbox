"""API Ninjas client for earnings call transcripts.

Uses the free API Ninjas Earnings Call Transcript API to fetch transcripts.
Sign up for a free API key at https://api-ninjas.com/
"""

import json
import logging
import urllib.request
import urllib.error
from datetime import date

logger = logging.getLogger(__name__)

BASE_URL = "https://api.api-ninjas.com/v1"


def _api_get(endpoint: str, params: dict, api_key: str) -> list | dict | None:
    """Make a GET request to the API Ninjas API. Returns parsed JSON or None on error."""
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}/{endpoint}?{query}"

    try:
        req = urllib.request.Request(url, headers={
            "X-Api-Key": api_key,
            "User-Agent": "EarningsCallAgent/1.0",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            logger.debug("API response for %s: %s", endpoint, raw[:500])
            data = json.loads(raw)
            if isinstance(data, dict) and "error" in data:
                logger.error("API Ninjas error: %s", data["error"])
                return None
            return data
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()
        except Exception:
            pass
        if e.code == 404:
            logger.debug("No data found for %s (404): %s", endpoint, body)
            return None
        logger.error("API Ninjas HTTP error %d for %s: %s — %s", e.code, endpoint, e.reason, body)
        return None
    except (urllib.error.URLError, TimeoutError) as e:
        logger.error("API Ninjas request failed for %s: %s", endpoint, e)
        return None


def get_recent_earnings(api_key: str, watchlist: list[str], days_back: int = 7) -> list[dict]:
    """Build a list of recent quarter candidates to check for each watchlist symbol.

    Calculates the current and previous quarter and creates candidates for
    each watchlist symbol. Returns list of dicts with keys: symbol, quarter, year.
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
    data = _api_get("earningscalltranscript", {
        "ticker": symbol,
        "quarter": quarter,
        "year": year,
    }, api_key)

    if not data:
        logger.warning("No transcript data for %s Q%d %d", symbol, quarter, year)
        return None

    # API Ninjas may return a single object or a list
    if isinstance(data, list):
        if len(data) == 0:
            logger.warning("Empty transcript list for %s Q%d %d", symbol, quarter, year)
            return None
        data = data[0]

    transcript = data.get("transcript", "")
    if transcript:
        logger.info("Fetched transcript for %s Q%d %d (%d chars)", symbol, quarter, year, len(transcript))
        return transcript

    logger.warning("Empty transcript for %s Q%d %d", symbol, quarter, year)
    return None
