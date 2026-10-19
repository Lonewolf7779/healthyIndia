"""
In-memory sliding-window rate limiter for healthyIndia API endpoints.

Provides defense-in-depth protection against resource exhaustion and brute-force abuse.
Applies per-client IP address rate limits partitioned by route category.

Note on multi-worker / distributed deployments:
This in-memory implementation operates on a per-process basis. In a clustered or
multi-worker deployment, application-level rate limiting should be complemented
by an edge reverse proxy (e.g., Nginx limit_req, Cloudflare, or AWS WAF) or a
centralized Redis token bucket as documented in docs/SECURITY.md.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import ClassVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings


@dataclass
class RateLimitRule:
    """Defines request limit per minute for a route pattern."""

    requests_per_minute: int
    window_seconds: float = 60.0


class InMemoryRateLimiter:
    """
    Sliding-window rate limiter using in-memory timestamp deques.
    Thread-safe and bounds memory consumption through automatic eviction.
    """

    DEFAULT_LIMITS: ClassVar[dict[str, RateLimitRule]] = {
        "/api/v1/extraction/ocr": RateLimitRule(requests_per_minute=10),
        "/api/v1/extraction/confirm": RateLimitRule(requests_per_minute=30),
        "/api/v1/nutrition/analyze": RateLimitRule(requests_per_minute=60),
        "/api/v1/ingredients/analyze": RateLimitRule(requests_per_minute=60),
    }

    def __init__(
        self,
        default_rpm: int = 120,
        rules: dict[str, RateLimitRule] | None = None,
        max_tracked_clients: int = 10000,
    ) -> None:
        self.default_rule = RateLimitRule(requests_per_minute=default_rpm)
        self.rules = rules or self.DEFAULT_LIMITS
        self.max_tracked_clients = max_tracked_clients
        self._lock = threading.Lock()
        # Mapping: client_key -> route_pattern -> list of timestamps
        self._history: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        self._last_cleanup: float = time.monotonic()

    def _resolve_rule(self, path: str) -> tuple[str, RateLimitRule]:
        """Resolves the rate limit rule for a given path."""
        for pattern, rule in self.rules.items():
            if path == pattern or path.startswith(pattern):
                return pattern, rule
        return "default", self.default_rule

    def _cleanup_stale_records(self, now: float) -> None:
        """Removes entries older than 2 minutes and enforces max tracked client bounds."""
        if now - self._last_cleanup < 60.0 and len(self._history) < self.max_tracked_clients:
            return
        cutoff = now - 120.0
        stale_clients = []
        for client_ip, route_map in list(self._history.items()):
            for route_key, timestamps in list(route_map.items()):
                valid_ts = [ts for ts in timestamps if ts > cutoff]
                if valid_ts:
                    route_map[route_key] = valid_ts
                else:
                    route_map.pop(route_key, None)
            if not route_map:
                stale_clients.append(client_ip)
        for client_ip in stale_clients:
            self._history.pop(client_ip, None)

        # If memory bounds are still exceeded after stale purging, evict oldest clients
        if len(self._history) >= self.max_tracked_clients:
            excess = len(self._history) - self.max_tracked_clients + 100
            for client_ip in list(self._history.keys())[:excess]:
                self._history.pop(client_ip, None)

        self._last_cleanup = now

    def check_rate_limit(self, client_ip: str, path: str) -> tuple[bool, int, float]:
        """
        Thread-safe check whether client_ip exceeds rate limit for the given path.

        Returns:
            tuple[bool, int, float]: (is_allowed, remaining_quota, retry_after_seconds)
        """
        with self._lock:
            now = time.monotonic()
            self._cleanup_stale_records(now)

            pattern_key, rule = self._resolve_rule(path)
            window_start = now - rule.window_seconds

            timestamps = self._history[client_ip][pattern_key]
            # Retain only timestamps within the active sliding window
            valid_timestamps = [t for t in timestamps if t > window_start]
            self._history[client_ip][pattern_key] = valid_timestamps

            if len(valid_timestamps) >= rule.requests_per_minute:
                # Over limit: retry after the oldest request in the window falls outside
                oldest_ts = valid_timestamps[0]
                retry_after = max(1.0, round(rule.window_seconds - (now - oldest_ts), 1))
                return False, 0, retry_after

            # Record this request
            valid_timestamps.append(now)
            remaining = rule.requests_per_minute - len(valid_timestamps)
            return True, remaining, 0.0

    def reset(self) -> None:
        """Resets all tracked history (used in test fixtures)."""
        with self._lock:
            self._history.clear()
            self._last_cleanup = time.monotonic()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware applying route-specific sliding window rate limits.
    """

    def __init__(self, app, settings: Settings, limiter: InMemoryRateLimiter | None = None):  # noqa: ANN001
        super().__init__(app)
        self.settings = settings
        self.limiter = limiter or InMemoryRateLimiter(
            default_rpm=settings.RATE_LIMIT_DEFAULT_RPM,
            rules={
                "/api/v1/extraction/ocr": RateLimitRule(
                    requests_per_minute=settings.RATE_LIMIT_OCR_RPM
                ),
                "/api/v1/extraction/confirm": RateLimitRule(
                    requests_per_minute=settings.RATE_LIMIT_CONFIRM_RPM
                ),
                "/api/v1/nutrition/analyze": RateLimitRule(
                    requests_per_minute=settings.RATE_LIMIT_ANALYSIS_RPM
                ),
                "/api/v1/ingredients/analyze": RateLimitRule(
                    requests_per_minute=settings.RATE_LIMIT_ANALYSIS_RPM
                ),
            },
        )

    def _extract_client_ip(self, request: Request) -> str:
        """
        Extracts client IP address safely, respecting configured trusted reverse proxies.

        Security rule:
        Never trust client-submitted X-Forwarded-For or CF-Connecting-IP headers unless
        the immediate upstream peer (request.client.host) is explicitly present in
        the configured TRUSTED_PROXIES list.
        """
        direct_ip = request.client.host if request.client and request.client.host else "127.0.0.1"

        if direct_ip in self.settings.TRUSTED_PROXIES:
            cf_ip = request.headers.get("cf-connecting-ip")
            if cf_ip and cf_ip.strip():
                return cf_ip.strip()

            forwarded_for = request.headers.get("x-forwarded-for")
            if forwarded_for and forwarded_for.strip():
                hops = [h.strip() for h in forwarded_for.split(",") if h.strip()]
                if hops:
                    return hops[0]

        return direct_ip

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        if not self.settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Do not rate limit CORS preflight OPTIONS requests
        if request.method == "OPTIONS":
            return await call_next(request)

        # Do not rate limit health check endpoints
        if request.url.path in ("/api/v1/health", "/api/v1/health/live", "/api/v1/health/ready"):
            return await call_next(request)

        client_ip = self._extract_client_ip(request)
        allowed, remaining, retry_after = self.limiter.check_rate_limit(client_ip, request.url.path)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please slow down and try again later.",
                    }
                },
                headers={
                    "Retry-After": str(int(retry_after)),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
