"""Deterministic headline normalization and conservative similarity helpers."""

from __future__ import annotations

import hashlib
import re
from collections import Counter

# Broad topic tokens that must NOT alone justify a merge.
BROAD_TOPIC_TERMS = frozenset(
    {
        "ai",
        "artificial",
        "intelligence",
        "ml",
        "machine",
        "learning",
        "model",
        "models",
        "llm",
        "llms",
        "openai",
        "google",
        "deepmind",
        "meta",
        "microsoft",
        "amazon",
        "nvidia",
        "tech",
        "technology",
        "startup",
        "startups",
        "research",
        "blog",
        "news",
        "update",
        "updates",
        "new",
        "launch",
        "launches",
        "announces",
        "announced",
        "introducing",
        "introduction",
    }
)

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "from",
        "by",
        "at",
        "is",
        "are",
        "as",
        "its",
        "it",
        "this",
        "that",
        "into",
        "over",
        "after",
        "before",
        "how",
        "why",
        "what",
        "when",
        "via",
        "vs",
        "using",
    }
)

KNOWN_ENTITIES = (
    "chatgpt",
    "gemini",
    "deepmind",
    "openai",
    "huggingface",
    "hugging face",
    "llama.cpp",
    "llamacpp",
    "nvidia",
    "anthropic",
    "claude",
    "mistral",
    "qwen",
    "pytorch",
    "tensorflow",
    "ollama",
    "techcrunch",
    "chatgpt wallet",
    "gemini 4 hydrogen",
    "gemini 4",
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9+.#/-]*", re.IGNORECASE)
_VERSION_RE = re.compile(r"\b(?:v(?:ersion)?\s*)?(\d+(?:\.\d+){0,3})\b", re.IGNORECASE)
_DATE_RE = re.compile(
    r"\b(?:20\d{2}|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\b",
    re.IGNORECASE,
)


def normalize_headline(title: str) -> str:
    """Lowercase, strip punctuation noise, drop stopwords."""
    text = title.lower()
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"\[.*?\]|\(.*?\)", " ", text)
    tokens = [t for t in _WORD_RE.findall(text) if t not in STOPWORDS]
    return " ".join(tokens)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _WORD_RE.findall(text or "")]


def content_tokens(text: str, *, limit: int = 400) -> set[str]:
    tokens = [t for t in tokenize(text) if t not in STOPWORDS and len(t) > 2]
    return set(tokens[:limit])


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def headline_token_set(title: str) -> set[str]:
    return set(normalize_headline(title).split())


def extract_entities(title: str, text: str = "") -> set[str]:
    """Lightweight entity cues: known orgs/products, versions, distinctive capitals."""
    blob = f"{title} {text[:2000]}".lower()
    found: set[str] = set()
    for ent in KNOWN_ENTITIES:
        if ent in blob:
            found.add(ent.replace(" ", ""))
    for match in _VERSION_RE.finditer(blob):
        found.add(f"ver:{match.group(1)}")
    # Distinctive multi-digit / product-like tokens from title
    for tok in tokenize(title):
        if len(tok) >= 5 and tok not in BROAD_TOPIC_TERMS and not tok.isdigit():
            if any(c.isdigit() for c in tok) or tok in {
                "hydrogen",
                "carbon",
                "wallet",
                "simready",
            }:
                found.add(tok)
    return found


def extract_dates(text: str) -> set[str]:
    return {m.group(0).lower() for m in _DATE_RE.finditer(text or "")}


def distinctive_overlap(a: set[str], b: set[str]) -> set[str]:
    """Overlap excluding broad topic terms."""
    return {x for x in (a & b) if x not in BROAD_TOPIC_TERMS and not x.startswith("ver:")}


def fingerprint_text(text: str) -> str:
    cleaned = " ".join(tokenize(text))
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:24]


def content_changed_meaningfully(
    old_text: str | None,
    new_text: str | None,
    *,
    min_jaccard_delta: float = 0.18,
) -> tuple[bool, dict[str, float | int]]:
    """
    Conservative content-change detector.

    HN score-only changes never call this with different text. Short/thin text
    requires a clearer delta to count as meaningful.
    """
    old = (old_text or "").strip()
    new = (new_text or "").strip()
    if old == new:
        return False, {"same": 1.0}
    if not old and new:
        return len(new) >= 280, {"old_len": 0, "new_len": len(new)}
    if old and not new:
        return False, {"new_empty": 1.0}

    a = content_tokens(old)
    b = content_tokens(new)
    sim = jaccard(a, b)
    # Meaningful update if similarity drops enough AND enough new tokens appear.
    new_only = len(b - a)
    thin = min(len(old), len(new)) < 280
    threshold = 0.72 if thin else 0.82
    meaningful = sim < threshold and new_only >= (4 if thin else 8)
    # Also accept strong absolute divergence
    if sim < (1.0 - min_jaccard_delta) and new_only >= 12:
        meaningful = True
    return meaningful, {"jaccard": round(sim, 4), "new_tokens": new_only, "thin": int(thin)}


def title_similarity(a: str, b: str) -> float:
    return jaccard(headline_token_set(a), headline_token_set(b))


def should_merge_candidates(
    *,
    title_a: str,
    title_b: str,
    text_a: str,
    text_b: str,
) -> tuple[bool, dict[str, object]]:
    """
    Conservative near-duplicate decision.

    Prefer false negatives. Broad shared topics (AI/OpenAI) are insufficient alone.
    """
    t_sim = title_similarity(title_a, title_b)
    ents_a = extract_entities(title_a, text_a)
    ents_b = extract_entities(title_b, text_b)
    dist = distinctive_overlap(ents_a, ents_b)
    versions_a = {e for e in ents_a if e.startswith("ver:")}
    versions_b = {e for e in ents_b if e.startswith("ver:")}
    version_overlap = versions_a & versions_b
    c_sim = jaccard(content_tokens(text_a), content_tokens(text_b))

    evidence: dict[str, object] = {
        "title_similarity": round(t_sim, 4),
        "content_similarity": round(c_sim, 4),
        "distinctive_entities": sorted(dist),
        "version_overlap": sorted(version_overlap),
        "entities_a": sorted(ents_a),
        "entities_b": sorted(ents_b),
    }

    strong_title = t_sim >= 0.72
    medium_title = t_sim >= 0.55
    strong_content = c_sim >= 0.62
    has_distinctive = len(dist) >= 1
    # Prefer product-like distinctive cues (wallet, hydrogen, chatgptwallet, …)
    strong_distinctive = any(
        x in dist
        for x in (
            "wallet",
            "chatgptwallet",
            "hydrogen",
            "gemini4hydrogen",
            "simready",
        )
    ) or any(len(x) >= 10 for x in dist)
    has_version = len(version_overlap) >= 1

    # Shared specific product entity can overcome low bag-of-words title overlap.
    if strong_distinctive and c_sim >= 0.28:
        evidence["reason"] = "strong_distinctive_product"
        return True, evidence

    # Hard reject: very weak overlap without a distinctive product cue
    if t_sim < 0.45 and c_sim < 0.55 and not strong_distinctive:
        evidence["reason"] = "weak_overlap"
        return False, evidence

    if strong_title and (has_distinctive or has_version or strong_content):
        evidence["reason"] = "strong_title_plus_signal"
        return True, evidence
    if medium_title and has_distinctive and has_version and c_sim >= 0.45:
        evidence["reason"] = "medium_title_entity_version"
        return True, evidence
    if strong_content and has_distinctive and t_sim >= 0.5:
        evidence["reason"] = "strong_content_plus_entity"
        return True, evidence
    if has_distinctive and c_sim >= 0.35 and t_sim >= 0.34:
        evidence["reason"] = "distinctive_product_overlap"
        return True, evidence

    evidence["reason"] = "conservative_reject"
    return False, evidence


def top_terms(text: str, n: int = 12) -> list[str]:
    counts = Counter(t for t in tokenize(text) if t not in STOPWORDS and len(t) > 3)
    return [w for w, _ in counts.most_common(n)]
