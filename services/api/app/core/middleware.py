from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Environment, Settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies baseline HTTP security headers according to docs/SECURITY.md.
    """

    def __init__(self, app, settings: Settings):  # noqa: ANN001
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        try:
            response = await call_next(request)
        except Exception:
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An unexpected error occurred. Please try again later.",
                    }
                },
            )

        # Baseline security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # HSTS is only active in production when HTTPS is terminated
        if self.settings.ENVIRONMENT == Environment.PRODUCTION:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforces maximum request body size to guard against oversized payload DoS.
    Differentiates standard JSON payloads from multipart upload endpoints.
    """

    def __init__(  # noqa: ANN001
        self, app, max_bytes: int, upload_max_bytes: int | None = None
    ):
        super().__init__(app)
        self.max_bytes = max_bytes
        self.upload_max_bytes = upload_max_bytes or max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                is_upload = request.url.path.startswith("/api/v1/extraction")
                limit = self.upload_max_bytes if is_upload else self.max_bytes

                if length > limit:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": f"Request body exceeds limit of {limit} bytes.",
                            }
                        },
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "BAD_REQUEST",
                            "message": "Invalid Content-Length header.",
                        }
                    },
                )

        return await call_next(request)
