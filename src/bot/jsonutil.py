from __future__ import annotations

import json
import re

_JSON_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


def extract_json(text: str):
    """Return the first top-level JSON object or array embedded in ``text``, or ``None``.

    LLMs often wrap JSON in prose or code fences; this pulls the outermost
    ``{...}`` / ``[...]`` span and parses it, returning ``None`` on any failure.
    """
    if not text:
        return None
    match = _JSON_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
