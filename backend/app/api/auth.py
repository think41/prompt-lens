import logging
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, status

from ..core.config import settings
from ..schemas.auth import TokenRequest, TokenResponse
from ..schemas.response import APIResponse, ResponseMeta

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", status_code=status.HTTP_200_OK)
def get_token(body: TokenRequest) -> APIResponse[TokenResponse]:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "developer_id": body.developer_id,
        "team_id": body.team_id,
        "role": body.role.value if hasattr(body.role, "value") else body.role,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return APIResponse(
        data=TokenResponse(token=token, expires_in=settings.jwt_expire_minutes * 60),
        meta=ResponseMeta(),
    )
