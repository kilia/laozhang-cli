class LaozhangCliError(Exception):
    exit_code = 1

    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


class InputValidationError(LaozhangCliError):
    exit_code = 2


class ApiError(LaozhangCliError):
    exit_code = 3


class StorageError(LaozhangCliError):
    exit_code = 4
