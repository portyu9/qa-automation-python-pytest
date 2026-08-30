"""Executable OpenAPI contracts for the repository-owned posts API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from openapi_schema_validator import OAS30Validator, validate as validate_instance
from openapi_spec_validator import validate as validate_spec
from openapi_spec_validator.readers import read_from_filename

from src.http_client import HttpClient

_CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contract" / "openapi.yaml"
_POST_REF = "#/components/schemas/Post"


def _load_contract() -> dict[str, Any]:
    spec, _ = read_from_filename(str(_CONTRACT_PATH))
    validate_spec(spec)
    return spec


def _response_schema(spec: dict[str, Any], path: str, status: str) -> dict[str, Any]:
    return spec["paths"][path]["get"]["responses"][status]["content"]["application/json"]["schema"]


@pytest.mark.contract
def test_openapi_document_is_valid_and_routes_reference_the_post_schema() -> None:
    spec = _load_contract()

    assert _response_schema(spec, "/posts", "200") == {
        "type": "array",
        "items": {"$ref": _POST_REF},
    }
    assert _response_schema(spec, "/posts/{id}", "200") == {"$ref": _POST_REF}
    assert "404" in spec["paths"]["/posts/{id}"]["get"]["responses"]


@pytest.mark.contract
def test_local_provider_responses_conform_to_committed_openapi(
    run_mock_api, local_api_settings
) -> None:
    spec = _load_contract()
    post_schema = spec["components"]["schemas"]["Post"]

    with HttpClient(local_api_settings) as transport:
        collection_response = transport.request("GET", "/posts")
        single_response = transport.request("GET", "/posts/1")
        missing_response = transport.request("GET", "/posts/999999")

    assert collection_response.status_code == 200
    collection = collection_response.json()
    assert isinstance(collection, list) and collection, "contract fixture must expose at least one post"
    for post in collection:
        validate_instance(post, post_schema, cls=OAS30Validator)

    assert single_response.status_code == 200
    validate_instance(single_response.json(), post_schema, cls=OAS30Validator)
    assert missing_response.status_code == 404
