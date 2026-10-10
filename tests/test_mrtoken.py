from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from novelvideo.api.routes import model_gateway
from novelvideo.mrtoken import discover_models, normalize_base_url
from novelvideo.newapi_provisioner import (
    AdminToken,
    NewApiProvisionerConfig,
    build_channel_payload,
    list_channel_types,
)


@pytest.mark.parametrize(
    "base", [None, "", "https://api.mrtoken.cn/", "https://api.mrtoken.cn/v1/"]
)
def test_normalize_platform_and_sdk_urls(base):
    assert normalize_base_url(base) == "https://api.mrtoken.cn"
    channel = build_channel_payload(
        provider="mrtoken",
        upstream_key="test-platform-key",
        model_mapping={"DC-test": "exact-platform-id"},
        base_url=base,
    )["channel"]
    assert channel["type"] == 1
    assert channel["name"] == "DC-mrtoken"
    assert channel["base_url"] == "https://api.mrtoken.cn"


@pytest.mark.parametrize(
    "base",
    [
        "ftp://example.com",
        "https://user:secret@example.com",
        "https://example.com?key=secret",
    ],
)
def test_reject_credentials_in_base_url(base):
    with pytest.raises(ValueError, match="without credentials or query"):
        normalize_base_url(base)


@respx.mock
async def test_discovery_uses_bearer_and_preserves_exact_ids():
    route = respx.get("https://api.mrtoken.cn/v1/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "Vendor/exact ID"},
                    {"id": "Vendor/exact ID"},
                    {"model": "ignore"},
                    {"id": ""},
                    {"id": "test-platform-key"},
                ],
            },
        )
    )
    assert await discover_models("test-platform-key", "https://api.mrtoken.cn/v1") == [
        "Vendor/exact ID"
    ]
    assert (
        route.calls.last.request.headers["Authorization"] == "Bearer test-platform-key"
    )


@respx.mock
async def test_empty_catalog_has_no_defaults():
    respx.get("https://api.mrtoken.cn/v1/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    assert await discover_models("test-platform-key") == []


@pytest.mark.parametrize("status", [301, 401, 403, 429, 502])
@respx.mock
async def test_error_bodies_and_redirects_never_expose_key(status):
    respx.get("https://api.mrtoken.cn/v1/models").mock(
        return_value=httpx.Response(
            status,
            json={"detail": "test-platform-key"},
            headers={"Location": "https://elsewhere.test"},
        )
    )
    with pytest.raises(ValueError) as error:
        await discover_models("test-platform-key")
    assert str(status) in str(error.value)
    assert "test-platform-key" not in str(error.value)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="test-platform-key"),
        httpx.Response(200, json={"models": []}),
    ],
)
@respx.mock
async def test_malformed_discovery_response_is_secret_free(response):
    respx.get("https://api.mrtoken.cn/v1/models").mock(return_value=response)
    with pytest.raises(ValueError) as error:
        await discover_models("test-platform-key")
    assert "test-platform-key" not in str(error.value)


@respx.mock
def test_channel_catalog_adds_mrtoken_using_openai_adapter():
    cfg = NewApiProvisionerConfig(
        "http://new-api:3000", "local", "unused", "root", 1000, "test"
    )
    admin = AdminToken(1, "root", "test-admin", False)
    respx.get("http://new-api:3000/api/channel/types").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": {"items": [{"type": 1, "provider": "openai", "status": 1}]},
            },
        )
    )
    channel = next(
        item for item in list_channel_types(cfg, admin) if item["provider"] == "mrtoken"
    )
    assert channel["type"] == 1
    assert channel["defaultBaseUrl"] == "https://api.mrtoken.cn"
    assert channel["capabilities"] == ["text", "vision", "image", "video", "audio"]


@respx.mock
def test_discovery_api_uses_saved_key_without_returning_it(monkeypatch):
    monkeypatch.setattr(model_gateway, "require_ce_gateway_management", lambda: None)
    monkeypatch.setattr(
        model_gateway,
        "get_newapi_provider_channel",
        lambda provider: {
            "upstreamKey": "test-platform-key",
            "baseUrl": "https://api.mrtoken.cn",
        },
    )
    respx.get("https://api.mrtoken.cn/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "exact-id"}]})
    )
    app = FastAPI()
    app.include_router(model_gateway.router)
    response = TestClient(app).post(
        "/model-gateway/custom/newapi/provider-channel/models",
        json={"provider": "mrtoken"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "data": {"models": ["exact-id"]}}
    assert "test-platform-key" not in response.text


@respx.mock
def test_invalid_key_prevents_channel_save(monkeypatch):
    monkeypatch.setattr(model_gateway, "require_ce_gateway_management", lambda: None)
    monkeypatch.setattr(
        model_gateway, "get_newapi_provider_channel", lambda provider: None
    )
    monkeypatch.setattr(
        model_gateway,
        "save_newapi_provider_channels",
        lambda *args, **kwargs: pytest.fail("must discover before saving"),
    )
    respx.get("https://api.mrtoken.cn/v1/models").mock(
        return_value=httpx.Response(401, text="test-platform-key")
    )
    app = FastAPI()
    app.include_router(model_gateway.router)
    response = TestClient(app).post(
        "/model-gateway/custom/newapi/provider-channels",
        json={
            "channels": [{"provider": "mrtoken", "upstreamKey": "test-platform-key"}]
        },
    )
    assert response.status_code == 400
    assert "test-platform-key" not in response.text


def test_saved_channel_normalizes_sdk_url(monkeypatch, tmp_path):
    from novelvideo import config, model_gateway_settings

    monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))
    channels = model_gateway_settings.save_newapi_provider_channels(
        [
            {
                "provider": "mrtoken",
                "upstreamKey": "test-platform-key",
                "baseUrl": "https://api.mrtoken.cn/v1",
            },
        ]
    )
    assert channels[0]["type"] == 1
    assert channels[0]["baseUrl"] == "https://api.mrtoken.cn"
