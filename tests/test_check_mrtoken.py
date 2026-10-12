from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import httpx
import respx


spec = importlib.util.spec_from_file_location(
    "check_mrtoken", Path(__file__).resolve().parents[1] / "scripts/check_mrtoken.py"
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def test_missing_credential_does_not_make_request(monkeypatch, capsys):
    monkeypatch.delenv("PLATFORM_API_KEY", raising=False)
    assert helper.main([]) == 2
    assert "PLATFORM_API_KEY" in capsys.readouterr().err


@respx.mock
def test_external_file_uses_fixed_platform_url(tmp_path, capsys):
    key_file = tmp_path / "credential.json"
    key_file.write_text(
        json.dumps({"url": "https://elsewhere.test", "key": "test-platform-key"}),
        encoding="utf-8-sig",
    )
    route = respx.get("https://api.mrtoken.cn/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "exact-id"}]})
    )
    assert helper.main(["--key-file", str(key_file)]) == 0
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-platform-key"
    output = capsys.readouterr()
    assert "exact-id" in output.out
    assert "test-platform-key" not in output.out + output.err
    assert len(list(tmp_path.iterdir())) == 1


def test_invalid_key_file_never_echoes_contents(tmp_path, capsys):
    key_file = tmp_path / "credential.json"
    key_file.write_text("invalid test-platform-key", encoding="utf-8")
    assert helper.main(["--key-file", str(key_file)]) == 2
    assert "test-platform-key" not in capsys.readouterr().err
