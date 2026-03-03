"""EarningsCall client for fetching earnings call transcripts.

Uses the earningscall Python library (https://earningscall.biz/).
Free tier: AAPL and MSFT. Sign up for a free API key for 5,000+ companies.
"""

import logging
from datetime import date

import earningscall
from earningscall import get_company

logger = logging.getLogger(__name__)


def configure(api_key: str | None = None) -> None:
    """Set the EarningsCall API key if provided."""
    if api_key:
        earningscall.api_key = api_key
        logger.info("EarningsCall API key configured")
    else:
        logger.warning("No EARNINGSCALL_API_KEY set — only AAPL and MSFT transcripts available")


def get_recent_earnings(watchlist: list[str], days_back: int = 7) -> list[dict]:
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


def get_transcript(symbol: str, quarter: int, year: int) -> str | None:
    """Fetch an earnings call transcript for a specific symbol, quarter, and year.

    Returns the transcript text or None if unavailable.
    """
    try:
        company = get_company(symbol)
        if company is None:
            logger.warning("Company not found: %s", symbol)
            return None

        transcript = company.get_transcript(year=year, quarter=quarter)
        if transcript is None or not transcript.text:
            logger.warning("No transcript for %s Q%d %d", symbol, quarter, year)
            return None

        logger.info("Fetched transcript for %s Q%d %d (%d chars)", symbol, quarter, year, len(transcript.text))
        return transcript.text
    except Exception as e:
        logger.error("Error fetching transcript for %s Q%d %d: %s", symbol, quarter, year, e)
        return None
