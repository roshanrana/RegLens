from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse


class RegLensError(Exception):
    """Base exception for domain-specific RegLens failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "reglens_error",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ConfigurationError(RegLensError):
    """Raised when configuration is invalid or incomplete."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            code="configuration_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class CorpusLoadError(RegLensError):
    """Raised when a corpus cannot be loaded into structured sections."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            code="corpus_load_error",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details=details,
        )


class ChunkingError(RegLensError):
    """Raised when section text cannot be chunked safely."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            code="chunking_error",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details=details,
        )


class DependencyUnavailableError(RegLensError):
    """Raised when an optional local dependency is unavailable."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            code="dependency_unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


def error_response(error: RegLensError, *, request_id: str) -> JSONResponse:
    payload: dict[str, Any] = {
        "error": {
            "code": error.code,
            "message": error.message,
            "request_id": request_id,
        }
    }
    if error.details:
        payload["error"]["details"] = error.details

    return JSONResponse(status_code=error.status_code, content=payload)
