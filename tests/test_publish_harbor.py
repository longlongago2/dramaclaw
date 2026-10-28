from __future__ import annotations

import importlib.util
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publish_harbor.py"
spec = importlib.util.spec_from_file_location("publish_harbor", SCRIPT)
assert spec is not None and spec.loader is not None
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


@pytest.fixture(autouse=True)
def tag_inputs(monkeypatch):
    class BuildDate(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 10, 19, 18, 0, 0)

    def git_output(command, *, cwd, text, stderr):
        assert command == ["git", "rev-parse", "--verify", "HEAD"]
        assert cwd == SCRIPT.parents[1]
        assert text is True
        assert stderr == subprocess.PIPE
        return "01f4db4f65dd30e0ca2af388be6acaab5c188be9\n"

    monkeypatch.setattr(publish, "datetime", BuildDate)
    monkeypatch.setattr(publish.subprocess, "check_output", git_output)


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
            ["--project", "team", "--username", "publisher"]
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
        ["docker", "push", f"{publish.REGISTRY}/team/{name}:20261019-01f4db4f"]
        for name in ("dramaclaw", "dramaclaw-gateway", "dramaclaw-frontend")
    ]
    output = capsys.readouterr().out
    assert "DRAMACLAW_VERSION=20261019-01f4db4f" in output
    assert "DRAMACLAW_GATEWAY_VERSION=20261019-01f4db4f" in output


def test_skip_build_still_logs_in_and_checks_all_sources(docker_calls):
    assert publish.main(["--skip-build"]) == 0
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
    assert publish.main([]) == 1
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
    assert "DRAMACLAW_VERSION=20261019-01f4db4f" in output
    assert output.count("+ docker push ") == 3
    assert "Publication complete" not in output


@pytest.mark.parametrize(
    "arguments",
    [
        ["--tag", "custom-tag"],
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


@pytest.mark.parametrize("error", [
    FileNotFoundError("git not found"),
    subprocess.CalledProcessError(128, ["git", "rev-parse"]),
])
def test_git_failure_stops_before_docker(monkeypatch, capsys, error):
    def fail_git(*args, **kwargs):
        raise error

    def forbidden(*args, **kwargs):
        pytest.fail("Git failure must stop before Docker")

    monkeypatch.setattr(publish.subprocess, "check_output", fail_git)
    monkeypatch.setattr(publish.subprocess, "run", forbidden)
    assert publish.main(["--dry-run"]) == 1
    output = capsys.readouterr()
    assert "Could not generate image tag from Git HEAD" in output.err
    assert "DRAMACLAW_VERSION=" not in output.out


def test_invalid_git_sha_stops_before_docker(monkeypatch, capsys):
    monkeypatch.setattr(publish.subprocess, "check_output", lambda *a, **kw: "bad-sha")
    assert publish.main(["--dry-run"]) == 1
    assert "invalid HEAD commit SHA" in capsys.readouterr().err
