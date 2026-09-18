"""Versioned shared contracts. Import concrete types from their domain modules."""

from .records import RECORD_ADAPTER, Record, RecordSet
from .validation import LinkError, validate_links

__all__ = ["RECORD_ADAPTER", "LinkError", "Record", "RecordSet", "validate_links"]
