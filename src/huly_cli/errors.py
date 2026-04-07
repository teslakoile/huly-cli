"""Error types for Huly CLI."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class HulyError(Exception):
    """Base error for all Huly CLI errors."""

    exit_code: int = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AuthError(HulyError):
    """Authentication/authorization error."""

    exit_code: int = 2


class NotFoundError(HulyError):
    """Resource not found."""

    exit_code: int = 1


class RateLimitError(HulyError):
    """Rate limit exceeded."""

    exit_code: int = 1

    def __init__(self, message: str, retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ServerError(HulyError):
    """Server-side error (5xx)."""

    exit_code: int = 1


class ConfigError(HulyError):
    """Configuration error."""

    exit_code: int = 1


def handle_error(err: HulyError) -> None:
    """Print error and exit with appropriate code."""
    # Import here to avoid circular imports
    from huly_cli.output import print_error

    hint: str | None = None
    if isinstance(err, AuthError):
        hint = "Run 'huly auth login' to authenticate."
    elif isinstance(err, ConfigError):
        hint = "Run 'huly auth login' or check your config file."
    elif isinstance(err, RateLimitError) and err.retry_after:
        hint = f"Retry after {err.retry_after:.0f} seconds."

    print_error(err.message, hint)
    sys.exit(err.exit_code)
