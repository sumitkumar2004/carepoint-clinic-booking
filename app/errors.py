class AppError(Exception):
    """An error that maps cleanly to an HTTP response."""

    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self):
        body = {"error": {"code": self.code, "message": self.message}}
        if self.details:
            body["error"]["details"] = self.details
        return body


def validation_error(details):
    return AppError(400, "validation_error", "Request validation failed.", details)


def not_found(what, id_):
    return AppError(404, "not_found", f"{what} {id_} was not found.")


def conflict(code, message):
    return AppError(409, code, message)
