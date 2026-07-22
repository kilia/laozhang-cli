class LaozhangCliError(Exception):
    exit_code = 1
    http_status: int | None = None


class InputValidationError(LaozhangCliError):
    exit_code = 2


class ApiError(LaozhangCliError):
    exit_code = 3


class StorageError(LaozhangCliError):
    exit_code = 4
