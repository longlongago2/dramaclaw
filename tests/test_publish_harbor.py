from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publish_harbor.py"
spec = importlib.util.spec_from_file_location("publish_harbor", SCRIPT)
assert spec is not None and spec.loader is not None
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


@pytest.fixture
def docker_calls(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(publish.shutil, "which", lambda name: "docker")

    def run(command, *, cwd, check):
        assert cwd == SCRIPT.parents[1]
        assert check is True
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish.subprocess, "run", run)
    return calls


def test_publishes_three_compose_compatible_images(docker_calls, capsys):
    assert (
        publish.main(
            ["--project", "team", "--tag", "release-1", "--username", "publisher"]
        )
        == 0
    )
    assert [
        "docker",
        "login",
        publish.REGISTRY,
        "--username",
        "publisher",
    ] in docker_calls
    assert [
        "docker",
        "compose",
        "-f",
        "docker-compose.yml",
        "build",
        "api",
        "newapi",
        "web",
    ] in docker_calls
    pushes = [call for call in docker_calls if call[1] == "push"]
    assert pushes == [
        ["docker", "push", f"{publish.REGISTRY}/team/{name}:release-1"]
        for name in ("dramaclaw", "dramaclaw-gateway", "dramaclaw-frontend")
    ]
    assert "DRAMACLAW_GATEWAY_VERSION=release-1" in capsys.readouterr().out


def test_skip_build_still_logs_in_and_checks_all_sources(docker_calls):
    assert publish.main(["--skip-build", "--tag", "release-1"]) == 0
    assert not any("build" in call for call in docker_calls)
    assert ["docker", "login", publish.REGISTRY] in docker_calls
    inspect = next(call for call in docker_calls if call[1:3] == ["image", "inspect"])
    assert inspect[-3:] == [source for source, _ in publish.IMAGES]


@pytest.mark.parametrize("failure", ["login", "build", "inspect", "push"])
def test_docker_failure_stops_publication(monkeypatch, capsys, failure):
    calls = []
    monkeypatch.setattr(publish.shutil, "which", lambda name: "docker")

    def run(command, **kwargs):
        calls.append(command)
        if failure in command:
            raise subprocess.CalledProcessError(7, command)

    monkeypatch.setattr(publish.subprocess, "run", run)
    assert publish.main(["--tag", "release-1"]) == 1
    assert failure in calls[-1]
    output = capsys.readouterr()
    assert "exit 7" in output.err
    assert "Publication complete" not in output.out
    assert "DRAMACLAW_VERSION=" not in output.out


def test_dry_run_never_executes_docker_and_generates_default_tag(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("dry run must not invoke Docker")

    monkeypatch.setattr(publish.subprocess, "run", forbidden)
    monkeypatch.setattr(publish.shutil, "which", forbidden)
    assert publish.main(["--dry-run"]) == 0
    output = capsys.readouterr().out
    assert re.search(r"DRAMACLAW_VERSION=\d{8}-\d{6}\b", output)
    assert output.count("+ docker push ") == 3
    assert "Publication complete" not in output


@pytest.mark.parametrize(
    "arguments",
    [
        ["--tag", "bad/tag"],
        ["--tag", "-bad"],
        ["--tag", "x" * 129],
        ["--project", "Team"],
        ["--project", "team/nested"],
    ],
)
def test_invalid_inputs_fail_before_docker(monkeypatch, arguments):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid input must not invoke Docker")

    monkeypatch.setattr(publish.subprocess, "run", forbidden)
    with pytest.raises(SystemExit) as exc:
        publish.main(arguments)
    assert exc.value.code == 2


def test_missing_docker_reports_failure(monkeypatch, capsys):
    monkeypatch.setattr(publish.shutil, "which", lambda name: None)
    assert publish.main([]) == 1
    assert "not found on PATH" in capsys.readouterr().err
