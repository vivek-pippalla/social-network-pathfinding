class AppError(Exception):
    def __init__(
        self, code: str, message: str, status: int, details: list | None = None
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or []


class UnavailableError(AppError):
    def __init__(self, component: str):
        super().__init__(
            "UNAVAILABLE",
            "A required service is unavailable.",
            503,
            [{"component": component}],
        )
