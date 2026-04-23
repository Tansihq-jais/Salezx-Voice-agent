"""Rate limiting middleware using an in-memory sliding window per tenant."""
import threading
import time
from collections import defaultdict, deque
from typing import Deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding window rate limiter."""

    def __init__(self, limit: int = 100, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._windows: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, tenant_id: str, endpoint: str = "") -> bool:
        """Return True if the request is allowed, False if rate limit exceeded."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            window = self._windows[tenant_id]
            # Prune timestamps outside the window
            while window and window[0] <= cutoff:
                window.popleft()

            if len(window) >= self.limit:
                return False

            window.append(now)
            return True

    def reset(self, tenant_id: str) -> None:
        """Clear the sliding window for a tenant (useful for tests)."""
        with self._lock:
            self._windows[tenant_id] = deque()

    def seconds_until_reset(self, tenant_id: str) -> int:
        """Return seconds until the oldest request in the window expires."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            window = self._windows[tenant_id]
            # Prune first so we get an accurate oldest entry
            while window and window[0] <= cutoff:
                window.popleft()

            if not window:
                return 0
            oldest = window[0]

        remaining = (oldest + self.window_seconds) - now
        return max(1, int(remaining) + 1)


# Paths that are exempt from rate limiting
_SKIP_PATHS = {"/health", "/exoml", "/call-status"}

# Upload endpoints get a stricter limit
_UPLOAD_LIMITER = SlidingWindowRateLimiter(limit=10, window_seconds=60)
_DEFAULT_LIMITER = SlidingWindowRateLimiter(limit=100, window_seconds=60)


def _is_upload_endpoint(path: str, method: str) -> bool:
    if path.startswith("/upload"):
        return True
    if path.startswith("/api/campaigns") and method == "POST":
        return True
    return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces per-tenant sliding window rate limits."""

    def __init__(self, app, default_limiter: SlidingWindowRateLimiter | None = None,
                 upload_limiter: SlidingWindowRateLimiter | None = None) -> None:
        super().__init__(app)
        self._default = default_limiter or _DEFAULT_LIMITER
        self._upload = upload_limiter or _UPLOAD_LIMITER

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip rate limiting for exempt paths
        if path in _SKIP_PATHS or path.startswith("/ws/"):
            return await call_next(request)

        # Resolve tenant identity
        tenant_id: str = getattr(request.state, "tenant_id", None) or (
            request.client.host if request.client else "unknown"
        )

        # Choose limiter based on endpoint type
        if _is_upload_endpoint(path, request.method):
            limiter = self._upload
        else:
            limiter = self._default

        if not limiter.check(tenant_id, path):
            retry_after = limiter.seconds_until_reset(tenant_id)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
