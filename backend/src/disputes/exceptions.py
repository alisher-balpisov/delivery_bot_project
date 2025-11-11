"""Custom exceptions for the disputes module."""


class DisputeError(Exception):
    """Base exception for dispute-related errors."""

    pass


class DisputeAccessDenied(DisputeError):
    """Raised when a user tries to access a dispute without permission."""

    pass


class DisputeActionError(DisputeError):
    """Raised for invalid actions on a dispute (e.g., creating a duplicate)."""

    pass
