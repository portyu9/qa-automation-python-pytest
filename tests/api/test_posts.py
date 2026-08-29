"""Posts API tests for domain behavior and the governed local HTTP boundary."""

from __future__ import annotations

from typing import Any

import pytest

from src.api_client import PostsClient
from src.http_client import HttpClient


@pytest.mark.api
def test_list_posts_delegates_transport_policy(mocker) -> None:
    sample: list[dict[str, Any]] = [
        {"id": 1, "title": "T1", "body": "B1"},
        {"id": 2, "title": "T2", "body": "B2"},
    ]
    transport = mocker.Mock(spec=HttpClient)
    response = mocker.Mock()
    response.json.return_value = sample
    transport.request.return_value = response

    posts = PostsClient(transport).list_posts()

    assert posts == sample
    transport.request.assert_called_once_with("GET", "/posts")
    response.raise_for_status.assert_called_once_with()


@pytest.mark.api
def test_list_posts_rejects_non_collection_payload(mocker) -> None:
    transport = mocker.Mock(spec=HttpClient)
    response = mocker.Mock()
    response.json.return_value = {"id": 1}
    transport.request.return_value = response

    with pytest.raises(ValueError, match="JSON array of objects"):
        PostsClient(transport).list_posts()


@pytest.mark.api
def test_list_posts_from_local_mock_server(run_mock_api, local_api_settings) -> None:
    with HttpClient(local_api_settings) as transport:
        posts = PostsClient(transport).list_posts()

    assert posts
    assert all(
        isinstance(post, dict) and {"id", "title", "body"}.issubset(post)
        for post in posts
    )