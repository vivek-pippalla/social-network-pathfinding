class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        details: list | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or []
        self.headers = headers or {}


class UnavailableError(AppError):
    def __init__(self, component: str):
        super().__init__(
            "UNAVAILABLE",
            "A required service is unavailable.",
            503,
            [{"component": component}],
        )


class EmailTakenError(AppError):
    def __init__(self):
        super().__init__(
            "EMAIL_TAKEN", "An account with this email already exists.", 409
        )


class RateLimitedError(AppError):
    def __init__(self, retry_after: int):
        super().__init__(
            "RATE_LIMITED",
            "Too many requests. Try again later.",
            429,
            headers={"Retry-After": str(max(1, retry_after))},
        )
