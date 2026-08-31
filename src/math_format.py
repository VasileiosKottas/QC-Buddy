"""Helpers to make LLM math output safer for Streamlit KaTeX."""

from __future__ import annotations

import re


_WRAPPED_ENV_RE = re.compile(
    r"\$\$\s*(\\begin\{(?:align\*?|equation\*?|aligned)\}.*?\\end\{(?:align\*?|equation\*?|aligned)\})\s*\$\$",
    flags=re.DOTALL,
)
_ALIGN_RE = re.compile(
    r"\\begin\{align\*?\}(.*?)\\end\{align\*?\}",
    flags=re.DOTALL,
)
_EQ_RE = re.compile(
    r"\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}",
    flags=re.DOTALL,
)
_ALIGNED_RE = re.compile(
    r"\\begin\{aligned\}(.*?)\\end\{aligned\}",
    flags=re.DOTALL,
)


def _lines_to_display_math(body: str) -> str:
    chunks: list[str] = []
    for raw_line in re.split(r"\\\\", body):
        line = raw_line.strip()
        if not line:
            continue
        line = line.replace("&=", "=").replace("&", "")
        line = re.sub(r"\\left|\\right", "", line)
        chunks.append(f"$$\n{line}\n$$")
    return "\n\n".join(chunks)


def sanitize_math_markdown(text: str) -> str:
    """Convert fragile LaTeX environments into simple $$...$$ blocks."""
    if not text:
        return text

    # Drop outer $$ around environments so we don't leave empty delimiters.
    cleaned = _WRAPPED_ENV_RE.sub(r"\1", text)
    cleaned = _ALIGN_RE.sub(lambda m: _lines_to_display_math(m.group(1)), cleaned)
    cleaned = _ALIGNED_RE.sub(lambda m: _lines_to_display_math(m.group(1)), cleaned)
    cleaned = _EQ_RE.sub(
        lambda m: f"$$\n{m.group(1).strip().replace('&=', '=').replace('&', '')}\n$$",
        cleaned,
    )
    cleaned = cleaned.replace("&=", "=")
    return cleaned
