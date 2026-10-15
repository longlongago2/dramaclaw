from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from scripts.compliance.update_license_inventory import update_inventory
from scripts.install_commit_hooks import install_hooks


ROOT = Path(__file__).resolve().parents[1]


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.STDOUT)


@pytest.fixture
def hooked_repo(tmp_path: Path):
    if shutil.which("pre-commit") is None:
        pytest.skip("pre-commit executable is required for the installed-hook integration test")
    git(tmp_path, "init", "-q")
    for name in [
        "scripts/install_commit_hooks.py", "scripts/lint_banned_words.py",
        "scripts/ce_allowlist.py", "ce-allowlist.toml",
        "scripts/compliance/update_license_inventory.py",
        "scripts/compliance/generate_p0b_artifacts.py",
    ]:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n- repo: local\n  hooks:\n"
        "  - id: license-inventory\n    name: inventory\n"
        "    entry: python -X utf8 -m scripts.compliance.update_license_inventory --check\n"
        "    language: system\n    pass_filenames: false\n    always_run: true\n"
        "  - id: banned-words\n    name: wording\n"
        "    entry: python -X utf8 scripts/lint_banned_words.py\n"
        "    language: system\n    files: '\\.md$'\n",
        encoding="utf-8",
    )
    (tmp_path / "draft.md").write_text("source-available\n", encoding="utf-8")
    (tmp_path / "license-inventory.csv").write_text("", encoding="utf-8")
    git(tmp_path, "add", ".")
    assert update_inventory(tmp_path, stage=True) == 0
    git(tmp_path, "-c", "user.name=Hook Test", "-c", "user.email=hook@example.invalid", "commit", "-qm", "baseline")
    install_hooks(tmp_path)
    # Reinstallation must keep one preparation block and working checks.
    install_hooks(tmp_path)
    return tmp_path


def test_commit_autogenerates_inventory_and_preserves_unstaged_text(hooked_repo: Path):
    root = hooked_repo
    (root / "新增 file.md").write_text("source-available\n", encoding="utf-8")
    git(root, "add", "新增 file.md")
    (root / "新增 file.md").write_text("open source unstaged draft\n", encoding="utf-8")
    (root / "draft.md").write_text("open source unrelated draft\n", encoding="utf-8")
    output = git(root, "-c", "user.name=Hook Test", "-c", "user.email=hook@example.invalid", "commit", "-qm", "add document")
    assert b"Passed" in output
    assert git(root, "show", "HEAD:新增 file.md") == b"source-available\n"
    assert "新增 file.md" in git(root, "show", "HEAD:license-inventory.csv").decode("utf-8")
    assert (root / "新增 file.md").read_text(encoding="utf-8") == "open source unstaged draft\n"
    assert (root / "draft.md").read_text(encoding="utf-8") == "open source unrelated draft\n"


def test_real_hook_blocks_stale_inventory_with_manual_changes(hooked_repo: Path):
    root = hooked_repo
    (root / "new.md").write_text("source-available\n", encoding="utf-8")
    git(root, "add", "new.md")
    inventory = root / "license-inventory.csv"
    inventory.write_text(inventory.read_text(encoding="utf-8") + "manual draft\n", encoding="utf-8")
    before = inventory.read_bytes()
    staged = git(root, "show", ":license-inventory.csv")
    result = subprocess.run(
        ["git", "-c", "user.name=Hook Test", "-c", "user.email=hook@example.invalid", "commit", "-qm", "blocked"],
        cwd=root, capture_output=True,
    )
    assert result.returncode != 0
    assert inventory.read_bytes() == before
    assert git(root, "show", ":license-inventory.csv") == staged


def test_real_hook_rejects_staged_forbidden_word(hooked_repo: Path):
    root = hooked_repo
    (root / "new.md").write_text("open source\n", encoding="utf-8")
    git(root, "add", "new.md")
    result = subprocess.run(
        ["git", "-c", "user.name=Hook Test", "-c", "user.email=hook@example.invalid", "commit", "-qm", "blocked"],
        cwd=root, capture_output=True,
    )
    assert result.returncode != 0
    assert b"wording" in result.stdout + result.stderr
    assert update_inventory(root, check=True) == 0
