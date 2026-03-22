"""Simple in-memory rate limiter per IP address."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Rate limit: max requests per window
MAX_REQUESTS = 5
WINDOW_SECONDS = 60

# Paths that consume API credits
LIMITED_PATHS = {"/api/extract", "/api/classify"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if request.method != "POST" or request.url.path not in LIMITED_PATHS:
            return await call_next(request)

        # Use X-Forwarded-For for proxied requests (Render), fallback to client IP
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not ip:
            ip = request.client.host if request.client else "unknown"

        now = time.time()
        window_start = now - WINDOW_SECONDS

        # Clean old entries and check count
        self._hits[ip] = [t for t in self._hits[ip] if t > window_start]

        if len(self._hits[ip]) >= MAX_REQUESTS:
            retry_after = int(self._hits[ip][0] + WINDOW_SECONDS - now) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )

        self._hits[ip].append(now)
        return await call_next(request)
