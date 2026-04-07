"""
Web scraper module for extracting content from customer websites.

Supports multiple source URLs (e.g. business site + Daf Zahav minisite).
All sources are scraped and their text is aggregated into a single document
before being sent to the LLM, giving it the full digital footprint.

Strategy:
  1. Try each URL in the list with requests + BeautifulSoup.
  2. Failed URLs are skipped with a warning (not a hard crash).
  3. If no URLs are provided, or ALL URLs fail, fall back to
     samples/sample_site.html so the pipeline always produces output.
"""

import logging
from pathlib import Path
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SAMPLE_PATH = Path(__file__).parent.parent / "samples" / "sample_site.html"

REQUEST_TIMEOUT = 12  # seconds

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def scrape_site(urls: List[str]) -> Tuple[str, List[str]]:
    """
    Scrape one or more URLs and aggregate their text content.

    Args:
        urls: List of URLs to scrape (business site, Daf Zahav page, etc.).
              Pass an empty list to skip straight to the sample fallback.

    Returns:
        (aggregated_text, sources_used) – where sources_used lists every URL
        (or 'sample:<filename>') that actually contributed content.
    """
    collected: List[Tuple[str, str]] = []  # (content, source_label)

    for url in urls:
        try:
            content, label = _scrape_url(url)
            collected.append((content, label))
        except Exception as exc:
            logger.warning(
                "Skipping '%s' (%s: %s).",
                url,
                type(exc).__name__,
                exc,
            )

    # Fallback: no URLs given, or every URL failed
    if not collected:
        logger.info("No live sources succeeded – loading sample fixture.")
        content, label = _load_sample()
        collected.append((content, label))

    sources_used = [label for _, label in collected]

    # Merge all sources into one document with clear section headers
    if len(collected) == 1:
        aggregated = collected[0][0]
    else:
        parts = []
        for text, label in collected:
            parts.append(f"=== מקור: {label} ===\n\n{text}")
        aggregated = "\n\n" + ("\n\n" + "─" * 60 + "\n\n").join(parts)

    logger.info(
        "Aggregated %d source(s) → %d chars total. Sources: %s",
        len(collected),
        len(aggregated),
        sources_used,
    )
    return aggregated, sources_used


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _scrape_url(url: str) -> Tuple[str, str]:
    """Fetch a live URL and return its cleaned text content."""
    logger.info("Fetching: %s", url)

    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"

    logger.info(
        "Fetched %d bytes (HTTP %s) from %s",
        len(response.content),
        response.status_code,
        url,
    )
    return _parse_html(response.text), url


def _load_sample() -> Tuple[str, str]:
    """Read and parse the bundled sample HTML fixture."""
    if not SAMPLE_PATH.exists():
        raise FileNotFoundError(
            f"Sample file not found at '{SAMPLE_PATH}'. "
            "Ensure samples/sample_site.html exists in the project root."
        )
    logger.info("Loading sample fixture: %s", SAMPLE_PATH)
    html = SAMPLE_PATH.read_text(encoding="utf-8")
    return _parse_html(html), f"sample:{SAMPLE_PATH.name}"


def _parse_html(html: str) -> str:
    """
    Parse raw HTML into clean, LLM-friendly plain text.

    - Removes <script>, <style>, <nav>, <footer>, <head>, <noscript>, <iframe>.
    - Prepends <title> and meta description for extra signal.
    - Collapses whitespace.
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "head", "noscript", "iframe"]):
        tag.decompose()

    sections: List[str] = []

    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        sections.append(f"TITLE: {title_tag.get_text(strip=True)}")

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        sections.append(f"META DESCRIPTION: {meta_desc['content'].strip()}")

    raw_lines = soup.get_text(separator="\n", strip=True).splitlines()
    body_lines = [ln.strip() for ln in raw_lines if ln.strip()]
    sections.append("\n".join(body_lines))

    full_text = "\n\n".join(sections)
    logger.debug("Extracted %d characters from source.", len(full_text))
    return full_text
