"""Token counting for eval — tiktoken (cl100k_base) with char/4 fallback."""

from __future__ import annotations

import json
from typing import Any

_ENCODING = None


def _encoding():
    global _ENCODING
    if _ENCODING is None:
        try:
            import tiktoken

            _ENCODING = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            _ENCODING = False
    return _ENCODING


def count_tokens(text: str) -> int:
    if not text:
        return 0
    enc = _encoding()
    if enc:
        return len(enc.encode(text))
    return max(1, len(text) // 4)


def count_json(obj: Any) -> int:
    return count_tokens(json.dumps(obj, ensure_ascii=False))
