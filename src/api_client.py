"""Domain-level posts API operations built on the governed HTTP transport."""

from __future__ import annotations

from typing import Any

from src.http_client import HttpClient


class PostsClient:
    """Expose posts-resource operations without duplicating transport policy."""

    def __init__(self, transport: HttpClient):
        self._transport = transport

    def list_posts(self) -> list[dict[str, Any]]:
        response = self._transport.request("GET", "/posts")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ValueError("posts response must be a JSON array of objects")
        return payload