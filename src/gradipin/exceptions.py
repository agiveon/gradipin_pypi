"""Exception hierarchy for the Gradipin client."""
from __future__ import annotations


class GradipinError(Exception):
    """Base exception for all Gradipin errors."""


class AuthenticationError(GradipinError):
    """The API key was missing, invalid, or revoked."""


class AppNotFoundError(GradipinError):
    """The named app doesn't exist on this account."""


class APIError(GradipinError):
    """The Gradipin backend returned an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ConfigurationError(GradipinError):
    """Required configuration (e.g. API key) was not found."""
