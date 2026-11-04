"""Shared OpenAPI response metadata for the API contract."""

from app.models.schemas import ErrorEnvelope

ERROR_DEFINITIONS = {
    "VALIDATION_ERROR": (422, "Request validation failed."),
    "UNAUTHENTICATED": (401, "Authentication is required or invalid."),
    "RATE_LIMITED": (429, "The request rate limit was exceeded."),
    "EMAIL_TAKEN": (409, "The email address is already registered."),
    "USER_NOT_FOUND": (404, "The requested user was not found."),
    "PATH_NOT_FOUND": (404, "No path exists within the configured depth."),
    "CANNOT_FRIEND_SELF": (400, "A user cannot create a friendship with themself."),
    "UNAVAILABLE": (503, "A required service is unavailable."),
    "INTERNAL": (500, "An internal error occurred."),
    "REQUEST_TOO_LARGE": (413, "The request body exceeds the configured limit."),
    "CONFLICT": (409, "The request conflicts with the current state."),
    "NOT_FOUND": (404, "The requested resource was not found."),
}


def documented_errors(*codes: str) -> dict[int, dict]:
    """Build response docs with an example that contract tests can inspect."""
    responses: dict[int, dict] = {}
    for code in codes:
        status, message = ERROR_DEFINITIONS[code]
        response = responses.setdefault(
            status,
            {
                "model": ErrorEnvelope,
                "description": message,
                "x-error-codes": [],
                "content": {"application/json": {"examples": {}}},
            },
        )
        response["x-error-codes"].append(code)
        response["description"] = "; ".join(response["x-error-codes"])
        response["content"]["application/json"]["examples"][code] = {
            "summary": code,
            "value": {
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": "example-request-id",
                    "details": [],
                }
            },
        }
        if code == "RATE_LIMITED":
            response["headers"] = {
                "Retry-After": {
                    "description": "Seconds until the rate-limit window resets.",
                    "schema": {"type": "integer", "minimum": 1},
                }
            }
        if code == "UNAVAILABLE":
            responses[504] = {
                "model": ErrorEnvelope,
                "description": "The database query timed out.",
                "x-error-codes": ["UNAVAILABLE"],
                "content": {
                    "application/json": {
                        "examples": {
                            "UNAVAILABLE": {
                                "summary": "UNAVAILABLE",
                                "value": {
                                    "error": {
                                        "code": "UNAVAILABLE",
                                        "message": "The database query timed out.",
                                        "request_id": "example-request-id",
                                        "details": [],
                                    }
                                },
                            }
                        }
                    }
                },
            }
    return responses


COMMON_ERROR_CODES = ("INTERNAL", "UNAVAILABLE", "REQUEST_TOO_LARGE")


def route_errors(*codes: str, protected: bool = False) -> dict[int, dict]:
    """Add the shared errors and route-specific errors for an operation."""
    all_codes = [*COMMON_ERROR_CODES, "VALIDATION_ERROR", *codes]
    if protected:
        all_codes.append("UNAUTHENTICATED")
    return documented_errors(*dict.fromkeys(all_codes))


COMMON_ERRORS = route_errors()
