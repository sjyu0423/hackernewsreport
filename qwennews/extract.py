"""Article body extraction with polite, policy-respecting fetching."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag

from qwennews.config import Config
from qwennews.http_client import BinaryContentError, ResponseTooLargeError, safe_get
from qwennews.models import ContentExtractionStatus
from qwennews.robots import RobotsChecker
from qwennews.urls import UnsafeURLError, is_hn_discussion_url, validate_public_http_url

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")
_INNER_BRACKET_RE = re.compile(r"\[[^\[\]]*\]")
_UI_BRACKET_INNER_RE = re.compile(
    r"(?is)^\s*(?:-?\d+|upvote\s+\d+|follow|team|article|published\b.*)\s*$"
)
_UPVOTE_RE = re.compile(r"\bUpvote\s+\d+\b", re.IGNORECASE)
_FOLLOW_RE = re.compile(r"\bFollow\b")
_BACK_TO_RE = re.compile(r"\bBack to Articles?\b", re.IGNORECASE)
_SHARE_DROPDOWN_RE = re.compile(r"\bShare Dropdown Menu\b", re.IGNORECASE)
_BREADCRUMB_RE = re.compile(r"\bBreadcrumb\b", re.IGNORECASE)


@dataclass(slots=True)
class ExtractionResult:
    text: str | None
    status: ContentExtractionStatus
    detail: str | None = None


def _decompose_chrome(root: Tag) -> None:
    """Remove common non-article chrome before text extraction."""
    for junk in root(
        ["script", "style", "noscript", "svg", "iframe", "form", "nav", "footer", "header", "aside"]
    ):
        junk.decompose()
    for tag in list(root.find_all(True)):
        if not isinstance(tag, Tag):
            continue
        role = (tag.get("role") or "").lower()
        classes = " ".join(tag.get("class") or []).lower()
        tid = (tag.get("id") or "").lower()
        aria = (tag.get("aria-label") or "").lower()
        if role in {"navigation", "banner", "contentinfo", "complementary"}:
            tag.decompose()
            continue
        if any(
            token in classes or token in tid or token in aria
            for token in (
                "upvote",
                "like-button",
                "share-button",
                "social-share",
                "breadcrumb",
                "navbar",
                "cookie",
            )
        ):
            tag.decompose()
            continue
        if tag.name in {"button", "a"} and any(
            token in classes or token in aria for token in ("upvote", "follow", "share")
        ):
            tag.decompose()


def _visible_text(node: Tag) -> str:
    _decompose_chrome(node)
    texts: list[str] = []
    for element in node.descendants:
        if isinstance(element, NavigableString):
            parent = element.parent
            if parent and parent.name in {"script", "style", "noscript"}:
                continue
            chunk = str(element).strip()
            if chunk:
                texts.append(chunk)
    return clean_extracted_text(" ".join(texts))


def _strip_ui_brackets(text: str) -> str:
    """Remove nested HF-style UI bracket chrome such as `[0 [0 Team ] Article ]`."""

    def repl(match: re.Match[str]) -> str:
        inner = match.group(0)[1:-1]
        if _UI_BRACKET_INNER_RE.match(inner):
            return " "
        if len(inner) < 48 and re.search(r"(?i)\b(published|team|article|upvote|follow)\b", inner):
            return " "
        if len(inner) < 12 and re.search(r"\d", inner) and "http" not in inner.lower():
            return " "
        return match.group(0)

    prev = None
    cleaned = text
    # Iterate so nested brackets peel from the inside out.
    while prev != cleaned:
        prev = cleaned
        cleaned = _INNER_BRACKET_RE.sub(repl, cleaned)
    return cleaned


def clean_extracted_text(text: str) -> str:
    """
    Strip common site chrome that survives HTML extraction.

    Targets Hugging Face blog UI residue (Back to Articles, Upvote N, bracket
    counter noise) and generic share/breadcrumb strings.
    """
    cleaned = _WHITESPACE_RE.sub(" ", text).strip()
    cleaned = _BACK_TO_RE.sub(" ", cleaned)
    cleaned = _UPVOTE_RE.sub(" ", cleaned)
    cleaned = _FOLLOW_RE.sub(" ", cleaned)
    cleaned = _SHARE_DROPDOWN_RE.sub(" ", cleaned)
    cleaned = _BREADCRUMB_RE.sub(" ", cleaned)
    cleaned = _strip_ui_brackets(cleaned)
    cleaned = re.sub(r"\[\s*\]", " ", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    return cleaned


def extract_text_from_html(html: str) -> str | None:
    """
    Best-effort main-content extraction from HTML.

    Prefers <article>/<main>, then falls back to the densest paragraph container.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag_name in ("article", "main"):
        candidate = soup.find(tag_name)
        if isinstance(candidate, Tag):
            text = _visible_text(candidate)
            if len(text) >= 120:
                return text

    # Fall back: choose the block with the most paragraph text.
    best_text = ""
    for block in soup.find_all(["div", "section"]):
        if not isinstance(block, Tag):
            continue
        paragraphs = block.find_all("p", recursive=True)
        if len(paragraphs) < 2:
            continue
        text = clean_extracted_text(
            " ".join(p.get_text(" ", strip=True) for p in paragraphs),
        )
        if len(text) > len(best_text):
            best_text = text

    if len(best_text) >= 120:
        return best_text

    # Last resort: meta description
    meta = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if isinstance(meta, Tag):
        content = meta.get("content")
        if content and str(content).strip():
            return str(content).strip()

    body = soup.body
    if isinstance(body, Tag):
        text = _visible_text(body)
        return text or None
    return None


class ContentExtractor:
    """Fetch and extract article text when legally/technically accessible."""

    def __init__(
        self,
        client: httpx.Client,
        config: Config,
        robots: RobotsChecker | None = None,
    ) -> None:
        self._client = client
        self._config = config
        self._robots = robots or RobotsChecker(
            client,
            max_bytes=config.max_response_bytes,
            user_agent=config.user_agent,
        )

    def extract(self, url: str) -> ExtractionResult:
        """Attempt extraction; never raises for expected failure modes."""
        if not url or not url.strip():
            return ExtractionResult(None, ContentExtractionStatus.SKIPPED, "empty url")

        if is_hn_discussion_url(url):
            return ExtractionResult(
                None,
                ContentExtractionStatus.SKIPPED,
                "HN discussion pages are not treated as article bodies",
            )

        try:
            validate_public_http_url(url, resolve_dns=True)
        except UnsafeURLError as exc:
            logger.warning("Unsafe URL rejected for extraction: %s (%s)", url, exc)
            return ExtractionResult(None, ContentExtractionStatus.UNSAFE_URL, str(exc))

        if self._config.respect_robots and not self._robots.allowed(url):
            logger.info("robots.txt disallows extraction for %s", url)
            return ExtractionResult(
                None,
                ContentExtractionStatus.BLOCKED,
                "disallowed by robots.txt",
            )

        try:
            response = safe_get(
                self._client,
                url,
                max_bytes=self._config.max_response_bytes,
                allowed_content_types=(
                    "text/html",
                    "application/xhtml+xml",
                    "text/plain",
                ),
            )
        except UnsafeURLError as exc:
            return ExtractionResult(None, ContentExtractionStatus.UNSAFE_URL, str(exc))
        except BinaryContentError as exc:
            return ExtractionResult(None, ContentExtractionStatus.SKIPPED, str(exc))
        except ResponseTooLargeError as exc:
            return ExtractionResult(None, ContentExtractionStatus.FAILED, str(exc))
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            # Auth / paywall-ish / bot challenges
            if status in {401, 403, 407, 429, 451}:
                return ExtractionResult(
                    None,
                    ContentExtractionStatus.BLOCKED,
                    f"HTTP {status}",
                )
            return ExtractionResult(None, ContentExtractionStatus.FAILED, f"HTTP {status}")
        except httpx.HTTPError as exc:
            return ExtractionResult(None, ContentExtractionStatus.FAILED, str(exc))

        content_type = (response.headers.get("Content-Type") or "").lower()
        if "text/plain" in content_type:
            text = response.text.strip() or None
            status = ContentExtractionStatus.SUCCESS if text else ContentExtractionStatus.FAILED
            return ExtractionResult(text, status, None if text else "empty body")

        text = extract_text_from_html(response.text)
        if text:
            return ExtractionResult(text, ContentExtractionStatus.SUCCESS)
        return ExtractionResult(
            None,
            ContentExtractionStatus.FAILED,
            "could not extract meaningful text",
        )
