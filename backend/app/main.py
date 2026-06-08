import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import health, ingest, sessions
from .core.config import settings
from .core.exceptions import AppException, ErrorCode
from .schemas.response import ErrorDetail, ErrorResponse, ResponseMeta

logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(
        "PromptLens starting — env=%s db=%s",
        settings.app_env,
        settings.database_url.split("@")[-1],
    )
    yield


app = FastAPI(title="PromptLens", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def _error_response(code: ErrorCode, message: str, http_status: int) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message),
        meta=ResponseMeta(),
    )
    return JSONResponse(status_code=http_status, content=body.model_dump(mode="json"))


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return _error_response(exc.error_code, exc.error_message, exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    message = "; ".join(
        f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in exc.errors()
    )
    return _error_response(ErrorCode.VALIDATION_ERROR, message, status.HTTP_422_UNPROCESSABLE_ENTITY)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _error_response(
        ErrorCode.INTERNAL_ERROR,
        "An unexpected error occurred",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(sessions.router)
