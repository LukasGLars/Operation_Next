"""Pulling a JSON array out of a model response.

Written after a run where 32 valid candidates were all dropped: the verdict array
was cut off by max_tokens, the regex found no closing bracket, and every
candidate came back "uncertain" — a token budget problem wearing the costume of a
validation verdict. Truncation is now its own exception so the caller can say so.

The other trap is bracket matching. A non-greedy `\\[.*?\\]` matches the first
bracket pair in the text, so a citation marker like "[1]" parses as an empty
result set and the whole pass looks like it found nothing.
"""
import json
import re


class TruncatedResponse(ValueError):
    """The response was cut off before the array closed."""


def parse_json_array(text):
    """Return the first JSON array in the text that actually parses.

    Raises TruncatedResponse when brackets are unbalanced (cut off mid-array),
    ValueError when there is no array at all.
    """
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    end = text.rfind("]")
    for start in (i for i, char in enumerate(text) if char == "["):
        if end < start:
            break
        try:
            value = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(value, list):
            return value

    if text.count("[") > text.count("]"):
        raise TruncatedResponse(
            f"response truncated before the array closed ({len(text)} chars) — "
            "lower the chunk size or raise max_tokens"
        )
    raise ValueError(f"no JSON array in response: {text[:200]}")
