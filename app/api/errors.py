import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from neo4j.exceptions import ServiceUnavailable, SessionExpired
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errors import AppError

logger = logging.getLogger(__name__)


def _error(
    request: Request,
    code: str,
    message: str,
    details: list | None = None,
    status: int = 500,
    headers=None,
):
    return JSONResponse(
        status_code=status,
        headers=headers,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", "-"),
                "details": details or [],
            }
        },
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return _error(
            request,
            exc.code,
            exc.message,
            exc.details,
            exc.status,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        details = [
            {
                "location": [str(part) for part in item.get("loc", ())],
                "type": str(item.get("type", "invalid")),
            }
            for item in exc.errors()
        ]
        return _error(
            request, "VALIDATION_ERROR", "Request validation failed.", details, 422
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException):
        mapping = {
            400: ("BAD_REQUEST", "The request cannot be processed."),
            401: ("UNAUTHENTICATED", "Authentication is required or invalid."),
            403: ("FORBIDDEN", "You are not allowed to perform this action."),
            404: ("NOT_FOUND", "The requested resource was not found."),
            405: ("METHOD_NOT_ALLOWED", "The method is not allowed for this resource."),
            409: ("CONFLICT", "The request conflicts with the current state."),
        }
        code, message = mapping.get(
            exc.status_code, ("HTTP_ERROR", "The request could not be completed.")
        )
        exception_name = type(exc).__name__
        if exc.status_code == 404 and exception_name == "UserNotFoundException":
            code = "USER_NOT_FOUND"
        elif exc.status_code == 404 and exception_name == "PathNotFoundException":
            code = "PATH_NOT_FOUND"
        elif (
            exc.status_code == 400
            and isinstance(exc.detail, str)
            and (
                "cannot add yourself" in exc.detail.lower()
                or "cannot remove yourself" in exc.detail.lower()
            )
        ):
            code = "CANNOT_FRIEND_SELF"
        return _error(
            request, code, message, status=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(ServiceUnavailable)
    @app.exception_handler(SessionExpired)
    async def neo4j_handler(request: Request, exc: Exception):
        return _error(
            request, "UNAVAILABLE", "A required service is unavailable.", status=503
        )

    @app.exception_handler(Exception)
    async def unexpected_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled application error",
            extra={"request_id": getattr(request.state, "request_id", "-")},
        )
        return _error(request, "INTERNAL", "An internal error occurred.", status=500)
