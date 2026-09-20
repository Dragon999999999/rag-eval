"""Synchronous test client for exercising the in-process mock target."""

import asyncio
from typing import Any

import httpx
from fastapi import FastAPI


class SyncASGIClient:
    """Expose an ASGI application through a synchronous HTTPX-like client.

    The current Starlette test client relies on a synchronous transport that is
    incompatible with the project's httpx version.  This adapter keeps E2E
    tests synchronous while using HTTPX's supported asynchronous ASGI
    transport for each request.
    """

    def __init__(self, app: FastAPI) -> None:
        """Create a client for the provided ASGI application."""
        self.app = app

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send one request and wait synchronously for its response."""
        return asyncio.run(self._request(method, url, **kwargs))

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send one request through an asynchronous in-process transport."""
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, url, **kwargs)

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Send a synchronous GET request."""
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Send a synchronous POST request."""
        return self.request("POST", url, **kwargs)
