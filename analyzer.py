"""Analyze earnings call transcripts using Claude."""

import logging

import anthropic

logger = logging.getLogger(__name__)


def analyze_transcript(
    transcript: str,
    symbol: str,
    quarter: int,
    year: int,
    prompt_template: str,
    model: str,
    api_key: str,
) -> str | None:
    """Send a transcript to Claude for analysis using the configured prompt.

    Returns the analysis text, or None on error.
    """
    prompt = prompt_template.format(
        symbol=symbol,
        quarter=f"Q{quarter}",
        year=year,
    )

    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}\n\n---\n\nTRANSCRIPT:\n\n{transcript}",
                }
            ],
        )

        analysis = message.content[0].text
        logger.info("Analysis complete for %s Q%d %d (%d chars)", symbol, quarter, year, len(analysis))
        return analysis

    except anthropic.APIError as e:
        logger.error("Claude API error for %s Q%d %d: %s", symbol, quarter, year, e)
        return None
