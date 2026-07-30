"""Error envelope.

Every error response is {"detail": ..., "code": ...} per docs/05_API_SPEC.md
section 2. FastAPI's defaults do not include a machine-readable code and its
validation errors use a different shape entirely, so both are normalised by the
handlers registered in main.py.
"""

from __future__ import annotations

from fastapi import HTTPException, status


class AppError(HTTPException):
    """HTTPException carrying a machine-readable code."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def validation_error(detail: str, code: str = "VALIDATION_ERROR") -> AppError:
    return AppError(status.HTTP_400_BAD_REQUEST, code, detail)


def unauthorized(detail: str = "Not authenticated", code: str = "UNAUTHORIZED") -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, code, detail)


def forbidden(detail: str, code: str = "FORBIDDEN") -> AppError:
    return AppError(status.HTTP_403_FORBIDDEN, code, detail)


def not_found(detail: str, code: str = "NOT_FOUND") -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, code, detail)


def conflict(detail: str, code: str) -> AppError:
    return AppError(status.HTTP_409_CONFLICT, code, detail)


def rate_limited(detail: str) -> AppError:
    return AppError(status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMITED", detail)


def service_unavailable(detail: str) -> AppError:
    return AppError(status.HTTP_503_SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE", detail)
