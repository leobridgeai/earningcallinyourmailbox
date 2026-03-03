#!/usr/bin/env python3
"""Earnings Call In Your Mailbox — automated earnings analysis agent.

Monitors your stock watchlist for new earnings calls, fetches transcripts,
analyzes them with Claude, and emails you the results.

Usage:
    python main.py              # Run the full pipeline
    python main.py --dry-run    # Analyze but don't send emails
    python main.py --days 14    # Look back 14 days instead of default 7
"""

import argparse
import logging
import sys

from config import load_config, load_watchlist
from transcript_client import get_recent_earnings, get_transcript
from analyzer import analyze_transcript
from emailer import send_email
from state import load_processed, save_processed, make_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Earnings Call In Your Mailbox")
    parser.add_argument("--dry-run", action="store_true", help="Analyze but don't send emails (print to stdout)")
    parser.add_argument("--days", type=int, default=7, help="Number of days to look back for earnings (default: 7)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    config = load_config()
    secrets = config["secrets"]
    watchlist = load_watchlist(config)
    email_config = config["email"]
    analysis_config = config["analysis"]

    logger.info("Watchlist: %s", ", ".join(watchlist))
    logger.info("Looking back %d days for earnings", args.days)

    # Load already-processed earnings
    processed = load_processed()
    logger.info("Already processed: %d earnings calls", len(processed))

    # Check for recent earnings
    earnings = get_recent_earnings(secrets["api_ninjas_key"], watchlist, days_back=args.days)

    if not earnings:
        logger.info("No symbols to check")
        return 0

    # Filter to only new (unprocessed) earnings
    new_earnings = []
    for e in earnings:
        key = make_key(e["symbol"], e["quarter"], e["year"])
        if key in processed:
            logger.info("Skipping %s (already processed)", key)
        else:
            new_earnings.append(e)

    if not new_earnings:
        logger.info("All recent earnings already processed")
        return 0

    logger.info("Found %d new earnings to process", len(new_earnings))
    errors = 0

    for earning in new_earnings:
        symbol = earning["symbol"]
        quarter = earning["quarter"]
        year = earning["year"]
        key = make_key(symbol, quarter, year)

        logger.info("Processing %s Q%d %d...", symbol, quarter, year)

        # Fetch transcript (None means no transcript exists for this quarter yet)
        transcript = get_transcript(secrets["api_ninjas_key"], symbol, quarter, year)
        if not transcript:
            logger.info("No transcript for %s Q%d %d — skipping", symbol, quarter, year)
            continue

        # Analyze with Claude
        analysis = analyze_transcript(
            transcript=transcript,
            symbol=symbol,
            quarter=quarter,
            year=year,
            prompt_template=analysis_config["prompt"],
            model=analysis_config["model"],
            api_key=secrets["anthropic_api_key"],
        )
        if not analysis:
            logger.error("Analysis failed for %s Q%d %d", symbol, quarter, year)
            errors += 1
            continue

        # Send or print
        if args.dry_run:
            print(f"\n{'='*60}")
            print(f"  {symbol} Q{quarter} {year} — Earnings Call Analysis")
            print(f"{'='*60}\n")
            print(analysis)
            print()
        else:
            success = send_email(
                symbol=symbol,
                quarter=quarter,
                year=year,
                analysis=analysis,
                email_config=email_config,
                smtp_password=secrets["smtp_password"],
            )
            if not success:
                errors += 1
                continue

        # Mark as processed
        processed.add(key)
        save_processed(processed)
        logger.info("Done: %s", key)

    if errors:
        logger.warning("Completed with %d error(s)", errors)
        return 1

    logger.info("All done — %d earnings processed successfully", len(new_earnings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
