"""Regression tests for Hugging Face / site chrome boilerplate stripping."""

from __future__ import annotations

from qwennews.extract import clean_extracted_text, extract_text_from_html

HF_NOISY_HTML = """
<html><body>
<nav>Site Nav</nav>
<article>
  <p>Back to Articles</p>
  <h1>llama.cpp v1.0.0 : A stronger foundation for the local AI ecosystem</h1>
  <div class="upvote-button" aria-label="Upvote">Upvote 181</div>
  <button class="follow">Follow</button>
  <p>[0 [0 Team ] Article ] [0 Published November 13, 2026 ]
  [-1 ] [0 [0 Upvote 181 ] ]</p>
  <p>llama.cpp 1.0.0 marks a stable release for local inference tooling
  used across the ecosystem.</p>
  <p>The release focuses on compatibility, packaging, and a clearer
  foundation for downstream apps.</p>
  <p>Contributors emphasize reliability for CPU and GPU backends without
  changing the core GGUF workflow.</p>
</article>
</body></html>
"""


def test_clean_extracted_text_strips_hf_chrome() -> None:
    noisy = (
        "Back to Articles llama.cpp v1.0.0 [0 [0 Team ] Article ] "
        "[0 Published November 13, 2026 ] Upvote 181 Follow "
        "llama.cpp 1.0.0 marks a stable release for local inference."
    )
    cleaned = clean_extracted_text(noisy)
    assert "Back to Articles" not in cleaned
    assert "Upvote" not in cleaned
    assert "Follow" not in cleaned
    assert "[0" not in cleaned
    assert "llama.cpp 1.0.0 marks a stable release" in cleaned


def test_extract_html_removes_hf_nav_upvote_boilerplate() -> None:
    text = extract_text_from_html(HF_NOISY_HTML)
    assert text is not None
    assert "stable release for local inference" in text
    assert "Back to Articles" not in text
    assert "Upvote" not in text
    assert "Site Nav" not in text
    # Bracket counter chrome should not dominate the extract.
    assert text.count("[") < 2
