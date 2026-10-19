import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_v1_router
from app.core.config import Environment, Settings, get_settings
from app.core.logging import setup_logging
from app.core.middleware import RequestSizeLimitMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_logging(debug=settings.DEBUG)
    logger.info(
        "Starting %s [environment=%s, version=%s]",
        settings.APP_NAME,
        settings.ENVIRONMENT.value,
        settings.APP_VERSION,
    )
    yield
    logger.info("Stopping %s", settings.APP_NAME)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    # Disable interactive docs in production unless explicitly needed
    docs_url = "/docs" if settings.ENVIRONMENT != Environment.PRODUCTION else None
    redoc_url = "/redoc" if settings.ENVIRONMENT != Environment.PRODUCTION else None
    openapi_url = "/openapi.json" if settings.ENVIRONMENT != Environment.PRODUCTION else None

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # 1. Request size limit middleware (innermost - bounds memory/payloads)
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_bytes=settings.MAX_REQUEST_BODY_BYTES,
        upload_max_bytes=settings.MAX_IMAGE_UPLOAD_BYTES,
    )

    # 2. Rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        settings=settings,
    )

    # 3. Baseline security headers
    app.add_middleware(
        SecurityHeadersMiddleware,
        settings=settings,
    )

    # 3. Restrictive CORS middleware
    # Note: allow_credentials is False because cookie/token auth is not used in Phase 1
    # and wildcard origins with credentials are explicitly forbidden.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
        max_age=600,
    )

    # Exception Handlers: Safe responses without internal stack traces or filesystem paths
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        sanitized_errors = []
        for error in exc.errors():
            sanitized_errors.append(
                {
                    "loc": [str(loc) for loc in error.get("loc", [])],
                    "msg": error.get("msg", "Invalid input"),
                    "type": error.get("type", "validation_error"),
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request payload failed schema validation.",
                    "details": sanitized_errors,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        if isinstance(exc.detail, dict):
            error_code = exc.detail.get("code", "HTTP_ERROR")
            error_msg = exc.detail.get("message", "An error occurred.")
        else:
            error_code = "HTTP_ERROR"
            error_msg = str(exc.detail)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": error_code,
                    "message": error_msg,
                }
            },
            headers=exc.headers,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            error_code = exc.detail.get("code", "HTTP_ERROR")
            error_msg = exc.detail.get("message", "An error occurred.")
        else:
            error_code = "HTTP_ERROR"
            error_msg = str(exc.detail)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": error_code,
                    "message": error_msg,
                }
            },
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log safe error message on server side with logger, do not return traceback to client
        logger.error("Unhandled server exception: %s", type(exc).__name__, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred. Please try again later.",
                }
            },
        )

    # Register routers
    app.include_router(api_v1_router, prefix="/api/v1")

    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings

    return app


app = create_app()
