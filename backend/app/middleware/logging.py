import json
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger("promptlens.http")


def _fmt(raw: bytes, content_type: str) -> str:
    if raw and "application/json" in content_type:
        try:
            return json.dumps(json.loads(raw), indent=2)
        except Exception:
            pass
    return raw.decode(errors="replace") if raw else ""


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()

        req_body = await request.body()
        req_ct = request.headers.get("content-type", "")
        log.info(
            "→ %s %s\n%s",
            request.method,
            request.url.path,
            _fmt(req_body, req_ct),
        )

        response = await call_next(request)

        # Consume and re-emit the response stream so we can log the body
        resp_body = b"".join([chunk async for chunk in response.body_iterator])
        resp_ct = response.headers.get("content-type", "")
        duration_ms = (time.perf_counter() - start) * 1000

        log.info(
            "← %s %s %d %.1fms\n%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            _fmt(resp_body, resp_ct),
        )

        return Response(
            content=resp_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
