"""Exceptions shared across the extraction runtime."""

from __future__ import annotations


class BookrefsError(Exception):
    """Base class for every error this package raises deliberately."""


class UnsupportedFormat(BookrefsError):
    """The file extension has no parser."""


class MissingDependency(BookrefsError):
    """A parser needs something that is not installed.

    Carries the remedy so callers can print an actionable message instead of a
    traceback: `--check` and the Step 1 preflight both rely on this.
    """

    def __init__(self, message: str, *, remedy: str = "") -> None:
        super().__init__(message)
        self.remedy = remedy


class ParseFailure(BookrefsError):
    """The file matched a parser but could not be read."""
