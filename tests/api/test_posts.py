# Minor note: added for commit message consistency
"""
API tests for the ``api_client`` module.

These tests demonstrate how I mock external HTTP calls using ``pytest‑mock``
and how to exercise the client against the local Flask mock server.  The
``run_mock_api`` and ``api_base_url`` fixtures from ``conftest.py`` spin up
the server and point the client at it.
"""

from __future__ import annotations

import importlib
from typing import List, Dict, Any

import pytest

import src.api_client as api_client


@pytest.mark.api
def test_fetch_posts_mocked(mocker) -> None:
    """Verify that ``fetch_posts`` returns JSON when ``requests.get`` is mocked."""
    sample: List[Dict[str, Any]] = [
        {"id": 1, "title": "T1", "body": "B1"},
        {"id": 2, "title": "T2", "body": "B2"},
    ]
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = sample
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mocker.patch("requests.get", return_value=mock_resp)

    posts = api_client.fetch_posts()
    assert posts == sample
    assert len(posts) == 2


@pytest.mark.api
def test_fetch_posts_from_mock_server(run_mock_api, api_base_url) -> None:
    """Verify that ``fetch_posts`` can retrieve posts from the local Flask server."""
    # Reload api_client so that it picks up the API_BASE_URL environment variable
    importlib.reload(api_client)
    posts = api_client.fetch_posts()
    assert isinstance(posts, list)
    # our mock dataset has three posts; assert at least one
    assert len(posts) >= 1
    assert all("id" in p and "title" in p and "body" in p for p in posts)
