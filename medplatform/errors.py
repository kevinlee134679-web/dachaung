class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(code)


class SchemaError(RuntimeError):
    """Messages are local diagnostics, not suitable for HTTP responses."""
