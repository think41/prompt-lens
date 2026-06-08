from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core.config import settings
from ..core.exceptions import AppException, ErrorCode

_bearer = HTTPBearer(auto_error=True)


def get_current_developer(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppException(ErrorCode.TOKEN_EXPIRED, "Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AppException(ErrorCode.INVALID_TOKEN, "Invalid authentication token") from exc

    developer_id = payload.get("developer_id")
    if not developer_id:
        raise AppException(ErrorCode.MISSING_CLAIM, "Token missing developer_id claim")

    return {
        "developer_id": developer_id,
        "team_id": payload.get("team_id", "default"),
        "role": payload.get("role", "developer"),
    }
