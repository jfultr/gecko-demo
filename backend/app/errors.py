"""Consistent public error responses for the v1 API."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .models.api import ErrorDetail, ErrorResponse


def api_error(
    status_code: int, code: str, message: str, retryable: bool = False
) -> HTTPException:
    """Build an HTTP error with a stable client-facing code."""
    detail = ErrorDetail(code=code, message=message, retryable=retryable)
    return HTTPException(status_code=status_code, detail=detail.model_dump())


def install_error_handlers(app: FastAPI) -> None:
    """Render FastAPI and application errors using the v1 ErrorResponse shape."""

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and {"code", "message"} <= detail.keys():
            error = ErrorDetail.model_validate(detail)
        elif exc.status_code == 404:
            error = ErrorDetail(code="NOT_FOUND", message="Resource not found.")
        else:
            error = ErrorDetail(
                code="INVALID_REQUEST" if exc.status_code < 500 else "INTERNAL_ERROR",
                message="Invalid request." if exc.status_code < 500 else "Internal server error.",
                retryable=exc.status_code >= 500,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error=error).model_dump(),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error=ErrorDetail(code="INVALID_REQUEST", message="Invalid request.")
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR", message="Internal server error.", retryable=True
                )
            ).model_dump(),
        )
