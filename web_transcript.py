"""Fetch and extract transcript text from a user-provided URL.

Handles HTML pages (Motley Fool articles, company IR pages, etc.) by
stripping tags and extracting readable text. This is a best-effort approach —
page layouts change, but it works well for most transcript publishers.
"""

import logging
import urllib.request
import urllib.error
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

# Tags whose content we skip entirely (scripts, styles, nav, etc.)
_SKIP_TAGS = frozenset({
    "script", "style", "nav", "header", "footer", "aside",
    "noscript", "iframe", "svg", "form", "button",
})

# Minimum character count for the extracted text to be considered valid
_MIN_TRANSCRIPT_LENGTH = 500


class _TextExtractor(HTMLParser):
    """Simple HTML-to-text converter that preserves paragraph structure."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "li", "tr"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in ("p", "div", "h1", "h2", "h3", "h4", "li", "tr"):
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # Collapse whitespace within lines, preserve paragraph breaks
        lines = []
        for line in raw.split("\n"):
            cleaned = " ".join(line.split())
            if cleaned:
                lines.append(cleaned)
        return "\n\n".join(lines)


def fetch_transcript_from_url(url: str) -> str | None:
    """Fetch a URL and extract readable transcript text from the HTML.

    Returns the extracted text, or None if the fetch fails or the page
    doesn't contain enough text to be a transcript.
    """
    logger.info("Fetching transcript from URL: %s", url)

    # Handle plain text URLs (some IR pages serve .txt files)
    if url.endswith(".txt"):
        return _fetch_plain_text(url)

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; EarningsCallAgent/1.0)",
            "Accept": "text/html,application/xhtml+xml,text/plain",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logger.error("Failed to fetch URL %s: %s", url, e)
        return None

    # If it's plain text, return directly
    if "text/plain" in content_type:
        text = body.strip()
        if len(text) >= _MIN_TRANSCRIPT_LENGTH:
            logger.info("Fetched plain text transcript (%d chars)", len(text))
            return text
        logger.warning("Plain text too short (%d chars) — probably not a transcript", len(text))
        return None

    # Parse HTML and extract text
    extractor = _TextExtractor()
    try:
        extractor.feed(body)
    except Exception as e:
        logger.error("Failed to parse HTML from %s: %s", url, e)
        return None

    text = extractor.get_text()

    if len(text) < _MIN_TRANSCRIPT_LENGTH:
        logger.warning("Extracted text too short (%d chars) from %s — probably not a transcript", len(text), url)
        return None

    logger.info("Extracted transcript from URL (%d chars)", len(text))
    return text


def _fetch_plain_text(url: str) -> str | None:
    """Fetch a plain .txt URL."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; EarningsCallAgent/1.0)",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace").strip()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logger.error("Failed to fetch %s: %s", url, e)
        return None

    if len(text) >= _MIN_TRANSCRIPT_LENGTH:
        logger.info("Fetched plain text transcript (%d chars)", len(text))
        return text

    logger.warning("Text file too short (%d chars)", len(text))
    return None
