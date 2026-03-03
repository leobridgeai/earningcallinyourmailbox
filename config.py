"""Load configuration from .env environment variables and config.yaml."""

import csv
import io
import logging
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent
CONFIG_FILE = CONFIG_DIR / "config.yaml"

REQUIRED_ENV_VARS = ["ANTHROPIC_API_KEY", "SMTP_PASSWORD"]


def load_config() -> dict:
    """Load and validate all configuration.

    Returns a dict with keys: watchlist, email, analysis, and secrets.
    """
    # Load .env file (works on Windows, Mac, and Linux)
    load_dotenv(CONFIG_DIR / ".env")

    # Load config.yaml
    if not CONFIG_FILE.exists():
        print(f"Error: {CONFIG_FILE} not found. Copy config.yaml.example and edit it.", file=sys.stderr)
        sys.exit(1)

    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)

    # Validate required sections
    for section in ("watchlist", "email", "analysis"):
        if section not in config:
            print(f"Error: '{section}' section missing from config.yaml", file=sys.stderr)
            sys.exit(1)

    # Load secrets from environment
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        print("Copy .env.example to .env and fill in your keys.", file=sys.stderr)
        sys.exit(1)

    config["secrets"] = {
        "anthropic_api_key": os.environ["ANTHROPIC_API_KEY"],
        "smtp_password": os.environ["SMTP_PASSWORD"],
        "earningscall_api_key": os.environ.get("EARNINGSCALL_API_KEY", ""),
    }

    return config


def load_watchlist(config: dict) -> tuple[list[str], dict[str, str]]:
    """Load the stock watchlist from a published Google Sheet CSV.

    Falls back to config.yaml fallback list if the sheet is unreachable.
    The Google Sheet should have ticker symbols in column A and optional
    transcript URLs in column B.

    Returns (tickers, transcript_urls) where transcript_urls maps ticker -> URL.
    """
    watchlist_config = config["watchlist"]
    sheet_url = watchlist_config.get("sheet_url", "")
    fallback = watchlist_config.get("fallback", [])

    if not sheet_url:
        logger.warning("No sheet_url configured, using fallback watchlist")
        return fallback, {}

    try:
        req = urllib.request.Request(sheet_url, headers={"User-Agent": "EarningsCallAgent/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as e:
        logger.warning("Failed to fetch watchlist sheet: %s — using fallback", e)
        return fallback, {}

    # Parse CSV: column A = ticker symbols, column B (optional) = transcript URL
    tickers = []
    transcript_urls = {}
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if not row:
            continue
        symbol = row[0].strip().upper()
        # Skip header rows and empty cells
        if not symbol or symbol in ("TICKER", "SYMBOL", "STOCK"):
            continue
        # Basic validation: tickers are 1-5 uppercase letters
        if symbol.isalpha() and 1 <= len(symbol) <= 5:
            tickers.append(symbol)
            # Check for optional transcript URL in column B
            if len(row) > 1:
                url = row[1].strip()
                if url.startswith("http://") or url.startswith("https://"):
                    transcript_urls[symbol] = url
                    logger.info("Transcript URL provided for %s", symbol)

    if not tickers:
        logger.warning("No valid tickers found in sheet, using fallback watchlist")
        return fallback, {}

    logger.info("Loaded %d tickers from Google Sheet: %s", len(tickers), ", ".join(tickers))
    if transcript_urls:
        logger.info("%d tickers have manual transcript URLs", len(transcript_urls))
    return tickers, transcript_urls
