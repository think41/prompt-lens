from fastapi import APIRouter

from ..schemas.response import APIResponse, ResponseMeta

router = APIRouter(tags=["health"])


@router.get("/health", response_model=APIResponse[dict])
def health() -> APIResponse[dict]:
    return APIResponse(data={"status": "ok"}, meta=ResponseMeta())
