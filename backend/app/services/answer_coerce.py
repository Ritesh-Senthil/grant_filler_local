"""Coerce and validate PATCH answer payloads against the question type."""

import re
from typing import Any

from app.models import Question

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def coerce_answer_value(question: Question, value: Any) -> Any:
    """
    Return a value safe to store in Answer.answer_value (JSON).
    Raises ValueError with a short message suitable for HTTP 422.
    """
    t = (question.q_type or "textarea").lower()
    opts = list(question.options or [])

    if t == "yes_no":
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if not isinstance(value, str):
            raise ValueError("Yes/No answers must be the string Yes or No")
        s = value.strip()
        if not s:
            return ""
        low = s.lower()
        if low in ("yes", "y", "true", "1"):
            return "Yes"
        if low in ("no", "n", "false", "0"):
            return "No"
        if s in ("Yes", "No"):
            return s
        raise ValueError("Yes/No answers must be Yes or No")

    if t == "single_choice":
        if not isinstance(value, str):
            raise ValueError("Expected a single string choice")
        s = value.strip()
        if not s:
            return ""
        if s not in opts:
            raise ValueError(f"Choice must be one of: {', '.join(opts)}")
        return s

    if t == "multi_choice":
        if not isinstance(value, list):
            raise ValueError("Expected a list of selected choices")
        out: list[str] = []
        for x in value:
            if not isinstance(x, str):
                raise ValueError("Each selected choice must be a string")
            if x not in opts:
                raise ValueError(f"Invalid choice: {x!r}")
            if x not in out:
                out.append(x)
        return out

    if t == "number":
        if value is None or value == "":
            return ""
        if isinstance(value, bool):
            raise ValueError("Invalid number")
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return ""
            try:
                return float(s) if "." in s else int(s)
            except ValueError as e:
                raise ValueError("Enter a valid number") from e
        raise ValueError("Expected a number")

    if t == "date":
        if value is None or value == "":
            return ""
        if not isinstance(value, str):
            raise ValueError("Date must be YYYY-MM-DD")
        s = value.strip()
        if not s:
            return ""
        if not _DATE_RE.match(s):
            raise ValueError("Date must be YYYY-MM-DD")
        return s

    # text, textarea, other
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        raise ValueError("Expected text")
    return str(value)
