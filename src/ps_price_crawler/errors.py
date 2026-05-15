from __future__ import annotations


class CrawlerParseError(ValueError):
    """Base class for crawler parser failures caused by embedded store data."""


class MissingEmbeddedStateError(CrawlerParseError):
    """Raised when required embedded JSON state is missing or malformed."""


class MissingRequiredFieldError(CrawlerParseError):
    """Raised when embedded data omits a required parser field."""


class AmbiguousCacheEntryError(CrawlerParseError):
    """Raised when embedded cache entries cannot be resolved deterministically."""
