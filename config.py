"""Load configuration from .env environment variables and config.yaml."""

import os
import sys
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent
CONFIG_FILE = CONFIG_DIR / "config.yaml"

REQUIRED_ENV_VARS = ["FMP_API_KEY", "ANTHROPIC_API_KEY", "SMTP_PASSWORD"]


def load_config() -> dict:
    """Load and validate all configuration.

    Returns a dict with keys: watchlist, email, analysis, and secrets.
    """
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
        "fmp_api_key": os.environ["FMP_API_KEY"],
        "anthropic_api_key": os.environ["ANTHROPIC_API_KEY"],
        "smtp_password": os.environ["SMTP_PASSWORD"],
    }

    return config
