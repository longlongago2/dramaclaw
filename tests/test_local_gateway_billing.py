from __future__ import annotations

import json

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from novelvideo import local_gateway_billing as billing
from novelvideo import model_gateway_settings as settings
from novelvideo.api.routes import model_gateway
from novelvideo.newapi_provisioner import AdminToken, NewApiProvisionerConfig


@pytest.fixture
def gateway(monkeypatch, tmp_path):
    monkeypatch.setenv("ST_EDITION", "ce")
    monkeypatch.delenv("ST_CONTROL_PLANE_DSN", raising=False)
    monkeypatch.setenv("NEWAPI_PROVISIONER_ENABLED", "true")
    monkeypatch.setattr(settings, "_settings_db_path", lambda: tmp_path / "settings.db")
    cfg = NewApiProvisionerConfig("http://gateway.test", "", "", "root", 1000, "DC")
    monkeypatch.setattr(billing, "get_provisioner_config", lambda: cfg)
    monkeypatch.setattr(
        billing,
        "ensure_admin_access_token",
        lambda _: AdminToken(1, "root", "test-admin", False),
    )
    options = {
        "GroupRatio": json.dumps({"default": 1.5, "vip": 0.8}),
        "GroupGroupRatio": json.dumps({"default": {"default": 1.2, "vip": 0.6}}),
        "SelfUseModeEnabled": "false",
        "quota_setting.enable_free_model_pre_consume": "true",
    }
    writes = []

    def read(request):
        assert request.headers["New-Api-User"] == "1"
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": [
                    {"key": key, "value": value} for key, value in options.items()
                ],
            },
        )

    def write(request):
        payload = json.loads(request.content)
        writes.append(payload)
        options[payload["key"]] = payload["value"]
        return httpx.Response(200, json={"success": True})

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://gateway.test/api/option/").mock(side_effect=read)
        route = mock.put("http://gateway.test/api/option/").mock(side_effect=write)
        yield options, writes, route, write


def test_disable_restore_preserves_unrelated_group_changes(gateway):
    options, writes, _, _ = gateway
    original = dict(options)
    assert billing.get_local_gateway_billing() == {
        "disabled": False,
        "group": "default",
    }
    assert billing.set_local_gateway_billing(disabled=True)["disabled"] is True
    assert json.loads(options["GroupRatio"]) == {"default": 0, "vip": 0.8}
    assert json.loads(options["GroupGroupRatio"])["default"]["default"] == 0
    assert options["SelfUseModeEnabled"] == "true"
    assert options["quota_setting.enable_free_model_pre_consume"] == "false"
    count = len(writes)
    billing.set_local_gateway_billing(disabled=True)
    assert len(writes) == count
    options["GroupRatio"] = json.dumps({"default": 0, "vip": 0.9, "new": 2})
    status = billing.set_local_gateway_billing(disabled=False)
    assert status["disabled"] is False
    assert json.loads(options["GroupRatio"]) == {"default": 1.5, "vip": 0.9, "new": 2}
    for key in original.keys() - {"GroupRatio"}:
        assert json.loads(options[key]) == json.loads(original[key])
    assert settings.get_local_billing_backup("http://gateway.test") == {}


def test_retry_after_partial_failure_keeps_original_settings(gateway):
    options, _, route, write = gateway
    original = dict(options)

    def fail(request):
        if json.loads(request.content)["key"] == "SelfUseModeEnabled":
            return httpx.Response(200, json={"success": False, "message": "not saved"})
        return write(request)

    route.mock(side_effect=fail)
    with pytest.raises(RuntimeError, match="not saved"):
        billing.set_local_gateway_billing(disabled=True)
    assert billing.get_local_gateway_billing()["disabled"] is False
    assert settings.get_local_billing_backup("http://gateway.test") == original
    route.mock(side_effect=write)
    billing.set_local_gateway_billing(disabled=True)
    billing.set_local_gateway_billing(disabled=False)
    for key in original:
        assert json.loads(options[key]) == json.loads(original[key])


def test_api_validates_boolean_and_reports_effective_state(gateway):
    app = FastAPI()
    app.include_router(model_gateway.router)
    with TestClient(app) as client:
        assert (
            client.post(
                "/model-gateway/custom/newapi/billing", json={"disabled": "false"}
            ).status_code
            == 422
        )
        result = client.post(
            "/model-gateway/custom/newapi/billing", json={"disabled": True}
        )
        assert result.status_code == 200
        assert result.json() == {
            "ok": True,
            "data": {"disabled": True, "group": "default"},
        }
        assert (
            client.get("/model-gateway/custom/newapi/billing").json() == result.json()
        )


def test_unsupported_gateway_does_not_change_billing(gateway):
    options, writes, _, _ = gateway
    options.pop("quota_setting.enable_free_model_pre_consume")
    with pytest.raises(RuntimeError, match="required billing settings"):
        billing.set_local_gateway_billing(disabled=True)
    assert writes == []
    assert settings.get_local_billing_backup("http://gateway.test") == {}


def test_api_does_not_expose_gateway_error_credentials(gateway):
    _, _, route, _ = gateway
    route.respond(200, json={"success": False, "message": "credential-canary"})
    app = FastAPI()
    app.include_router(model_gateway.router)
    with TestClient(app) as client:
        result = client.post(
            "/model-gateway/custom/newapi/billing", json={"disabled": True}
        )
        assert result.status_code == 502
        assert "credential-canary" not in result.text


@pytest.mark.parametrize("method", ["get", "post"])
def test_ee_rejected_before_gateway_access(monkeypatch, method):
    monkeypatch.setenv("ST_EDITION", "ee")
    monkeypatch.setattr(
        billing,
        "get_provisioner_config",
        lambda: pytest.fail("must not access local gateway"),
    )
    app = FastAPI()
    app.include_router(model_gateway.router)
    with TestClient(app) as client:
        response = client.request(
            method,
            "/model-gateway/custom/newapi/billing",
            **({"json": {"disabled": True}} if method == "post" else {}),
        )
        assert response.status_code == 403
