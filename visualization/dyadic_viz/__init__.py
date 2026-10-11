"""Exact trace validation and event-driven synthesis visualization.

The lightweight package entry point deliberately does not import Manim.
"""

from .trace import load_trace
from .validation import TraceValidationError, ValidationReport, validate_trace

__all__ = ["load_trace", "TraceValidationError", "ValidationReport", "validate_trace"]
