"""Make arbitrary Python values safe for strict JSON (Starlette: allow_nan=False).

Stored answer_value may contain float('nan'), float('inf') from edge-case numeric input or
legacy data — json.dumps then raises ValueError and FastAPI returns 500.
"""

from __future__ import annotations

import json
import math
from typing import Any

_MAX_DEPTH = 48
_MAX_LIST = 10_000
_MAX_DICT = 5000


def sanitize_answer_value_for_api(val: Any) -> Any:
    """Return a value that json.dumps(..., allow_nan=False) accepts, or None."""
    if val is None:
        return None
    try:
        json.dumps(val, allow_nan=False)
        return val
    except (TypeError, ValueError, OverflowError, RecursionError):
        return _coerce_json_safe(val, depth=0)


def _coerce_json_safe(val: Any, *, depth: int) -> Any:
    if depth > _MAX_DEPTH:
        return None
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val
    if isinstance(val, int) and not isinstance(val, bool):
        return val
    if isinstance(val, float):
        return None if (math.isnan(val) or math.isinf(val)) else val
    if isinstance(val, list):
        return [_coerce_json_safe(x, depth=depth + 1) for x in val[:_MAX_LIST]]
    if isinstance(val, dict):
        out: dict[str, Any] = {}
        for i, (k, v) in enumerate(val.items()):
            if i >= _MAX_DICT:
                break
            out[str(k)] = _coerce_json_safe(v, depth=depth + 1)
        return out
    return str(val)
