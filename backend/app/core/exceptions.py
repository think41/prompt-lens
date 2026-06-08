from enum import StrEnum

from fastapi import HTTPException, status


class ErrorCode(StrEnum):
    # Auth
    UNAUTHORIZED = "UNAUTHORIZED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    MISSING_CLAIM = "MISSING_CLAIM"
    # Resources
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    # Ingest
    DUPLICATE_EVENT = "DUPLICATE_EVENT"
    # General
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_STATUS_MAP: dict[ErrorCode, int] = {
    ErrorCode.UNAUTHORIZED: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.TOKEN_EXPIRED: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.INVALID_TOKEN: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.MISSING_CLAIM: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.SESSION_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.DUPLICATE_EVENT: status.HTTP_409_CONFLICT,
    ErrorCode.VALIDATION_ERROR: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


class AppException(HTTPException):
    def __init__(self, code: ErrorCode, message: str) -> None:
        self.error_code = code
        self.error_message = message
        super().__init__(status_code=_STATUS_MAP[code], detail=message)
