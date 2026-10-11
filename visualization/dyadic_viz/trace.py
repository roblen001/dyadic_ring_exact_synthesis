"""Strict JSON loading for externally supplied synthesis traces."""

import json
from pathlib import Path


class TraceValidationError(ValueError):
    """A trace is malformed or its supplied mathematical claims disagree."""


def _object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TraceValidationError(f"JSON object: duplicate key {key!r}")
        result[key] = value
    return result


def _reject_constant(value):
    raise TraceValidationError(f"JSON: non-finite number {value!r} is not permitted")


def load_trace(path) -> dict:
    """Load UTF-8 JSON, rejecting duplicate keys and non-JSON numeric constants."""
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as source:
            trace = json.load(
                source,
                object_pairs_hook=_object_without_duplicates,
                parse_constant=_reject_constant,
            )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TraceValidationError(f"{path}: cannot read trace: {exc}") from exc
    if not isinstance(trace, dict):
        raise TraceValidationError("$: trace root must be a JSON object")
    return trace
