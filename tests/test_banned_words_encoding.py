from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/lint_banned_words.py"


@pytest.mark.parametrize("forbidden", [False, True])
def test_reports_work_when_parent_process_uses_gbk(tmp_path: Path, forbidden: bool):
    source = tmp_path / "说明📄.md"
    source.write_text("open source 📄\n" if forbidden else "source available 📄\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "gbk"},
        capture_output=True,
    )
    output = (result.stdout + result.stderr).decode("utf-8")
    assert result.returncode == (1 if forbidden else 0), output
    assert "UnicodeEncodeError" not in output
    assert "禁用词" in output
    if forbidden:
        assert "说明📄.md" in output
        assert "open source 📄" in output


def test_git_discovery_scans_unicode_filenames_under_gbk(tmp_path: Path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "文档📄.md"
    source.write_text("open source\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", source.name], check=True)
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "gbk"},
        capture_output=True,
    )
    output = (result.stdout + result.stderr).decode("utf-8")
    assert result.returncode == 1, output
    assert "文档📄.md" in output
    assert "UnicodeEncodeError" not in output
