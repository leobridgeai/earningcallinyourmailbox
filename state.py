"""Track which earnings calls have already been processed."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).parent / "processed.json"


def make_key(symbol: str, quarter: int, year: int) -> str:
    """Create a unique key for an earnings call."""
    return f"{symbol}:Q{quarter}:{year}"


def load_processed(path: Path = STATE_FILE) -> set[str]:
    """Load the set of already-processed earnings call keys."""
    if not path.exists():
        return set()

    try:
        with open(path) as f:
            data = json.load(f)
            return set(data)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Corrupted state file %s, starting fresh", path)
        return set()


def save_processed(processed: set[str], path: Path = STATE_FILE) -> None:
    """Persist the set of processed earnings call keys."""
    with open(path, "w") as f:
        json.dump(sorted(processed), f, indent=2)
    logger.info("Saved %d processed entries", len(processed))
