from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id", "").strip() or str(uuid4())
        request.state.request_id = request_id[:128]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """Small fixed-window limiter for a single API process.

    It is deliberately documented as a local/demo safeguard. Multi-replica
    deployments should enforce limits in a shared system such as Azure API
    Management or Redis.
    """

    def __init__(
        self,
        app: object,
        *,
        enabled: bool,
        requests: int,
        window_seconds: int,
        api_prefix: str,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.limit = requests
        self.window_seconds = window_seconds
        self.api_prefix = api_prefix
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._should_limit(request):
            return await call_next(request)

        now = time.monotonic()
        key = self._key(request)
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - events[0])))
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                    content={
                        "detail": {
                            "code": "rate_limit_exceeded",
                            "message": "Too many requests. Retry later.",
                        }
                    },
                )
            events.append(now)
            remaining = max(0, self.limit - len(events))

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = str(self.window_seconds)
        return response

    def _should_limit(self, request: Request) -> bool:
        if not self.enabled or request.method == "OPTIONS":
            return False
        if not request.url.path.startswith(self.api_prefix):
            return False
        return "/health" not in request.url.path

    def _key(self, request: Request) -> str:
        credential = request.headers.get("authorization") or request.headers.get("x-api-key")
        if credential:
            return "credential:" + hashlib.sha256(credential.encode("utf-8")).hexdigest()
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"
