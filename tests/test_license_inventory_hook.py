from __future__ import annotations

import csv
from pathlib import Path
import subprocess

import pytest

from scripts.compliance.generate_p0b_artifacts import render_license_inventory
from scripts.compliance.update_license_inventory import update_inventory


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.STDOUT)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init")
    (tmp_path / "existing.py").write_text("# existing\n", encoding="utf-8")
    (tmp_path / "license-inventory.csv").write_text(
        render_license_inventory(["existing.py", "license-inventory.csv"]),
        encoding="utf-8", newline="",
    )
    git(tmp_path, "add", "existing.py", "license-inventory.csv")
    return tmp_path


def inventory_paths(root: Path) -> set[str]:
    with (root / "license-inventory.csv").open(encoding="utf-8", newline="") as handle:
        return {row["path"] for row in csv.DictReader(handle)}


def test_staged_addition_is_generated_but_neither_untracked_files_nor_index_are_changed(repo: Path):
    (repo / "new file.py").write_text("# staged\n", encoding="utf-8")
    (repo / "not-staged.py").write_text("# local\n", encoding="utf-8")
    git(repo, "add", "new file.py")
    original_index = git(repo, "show", ":license-inventory.csv")
    assert update_inventory(repo) == 1
    assert "new file.py" in inventory_paths(repo)
    assert "not-staged.py" not in inventory_paths(repo)
    assert git(repo, "show", ":license-inventory.csv") == original_index
    git(repo, "add", "license-inventory.csv")
    before = (repo / "license-inventory.csv").read_bytes()
    assert update_inventory(repo) == 0
    assert (repo / "license-inventory.csv").read_bytes() == before


def test_check_rejects_stale_index_even_when_worktree_is_updated(repo: Path):
    (repo / "new.py").write_text("# staged\n", encoding="utf-8")
    git(repo, "add", "new.py")
    assert update_inventory(repo) == 1
    before = (repo / "license-inventory.csv").read_bytes()
    original_index = git(repo, "show", ":license-inventory.csv")
    assert update_inventory(repo, check=True) == 1
    assert (repo / "license-inventory.csv").read_bytes() == before
    assert git(repo, "show", ":license-inventory.csv") == original_index
    git(repo, "add", "license-inventory.csv")
    assert update_inventory(repo, check=True) == 0


def test_check_does_not_autofix_inventory_when_unstaged_changes_are_hidden(repo: Path):
    (repo / "new.py").write_text("# staged\n", encoding="utf-8")
    git(repo, "add", "new.py")
    before = (repo / "license-inventory.csv").read_bytes()
    assert update_inventory(repo, check=True) == 1
    assert (repo / "license-inventory.csv").read_bytes() == before


def test_check_validates_index_and_preserves_unstaged_manual_edits(repo: Path):
    path = repo / "license-inventory.csv"
    path.write_text("local edits\n", encoding="utf-8")
    assert update_inventory(repo, check=True) == 0
    assert path.read_text(encoding="utf-8") == "local edits\n"


def test_check_missing_inventory_does_not_create_it(repo: Path):
    git(repo, "rm", "--cached", "license-inventory.csv")
    (repo / "license-inventory.csv").unlink()
    assert update_inventory(repo, check=True) == 1
    assert not (repo / "license-inventory.csv").exists()


def test_staged_rename_and_deletion_follow_index_not_worktree(repo: Path):
    git(repo, "mv", "existing.py", "renamed.py")
    assert update_inventory(repo) == 1
    assert "existing.py" not in inventory_paths(repo)
    assert "renamed.py" in inventory_paths(repo)
    git(repo, "add", "license-inventory.csv")
    git(repo, "rm", "--cached", "renamed.py")
    assert (repo / "renamed.py").exists()
    assert update_inventory(repo) == 1
    assert "renamed.py" not in inventory_paths(repo)


@pytest.mark.parametrize("stage_manual_edit", [False, True])
def test_manual_metadata_is_not_overwritten(repo: Path, stage_manual_edit: bool):
    path = repo / "license-inventory.csv"
    text = path.read_text(encoding="utf-8").replace(
        "existing.py,Elastic-2.0,2026 SuperTale contributors",
        "existing.py,MIT,Reviewed owner",
    )
    path.write_text(text, encoding="utf-8")
    if stage_manual_edit:
        git(repo, "add", "license-inventory.csv")
    original = path.read_bytes()
    assert update_inventory(repo) == 1
    assert path.read_bytes() == original


def test_missing_inventory_can_be_bootstrapped(repo: Path):
    git(repo, "rm", "--cached", "license-inventory.csv")
    (repo / "license-inventory.csv").unlink()
    assert update_inventory(repo) == 1
    assert "existing.py" in inventory_paths(repo)


def test_unstaged_inventory_deletion_is_preserved(repo: Path):
    (repo / "license-inventory.csv").unlink()
    assert update_inventory(repo) == 1
    assert not (repo / "license-inventory.csv").exists()


def test_inventory_must_remain_in_the_index(repo: Path):
    git(repo, "rm", "--cached", "license-inventory.csv")
    before = (repo / "license-inventory.csv").read_bytes()
    assert update_inventory(repo) == 1
    assert (repo / "license-inventory.csv").read_bytes() == before


def test_third_party_metadata_uses_generator_overrides(repo: Path):
    asset = repo / "frontend/public/viewer-kit/quaternius/model.glb"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"test")
    git(repo, "add", "frontend")
    assert update_inventory(repo) == 1
    with (repo / "license-inventory.csv").open(encoding="utf-8", newline="") as handle:
        row = next(row for row in csv.DictReader(handle) if row["path"].endswith("model.glb"))
    assert row["license_expression"] == "CC0-1.0"
    assert row["copyright"] == "Quaternius"


def test_auto_stage_uses_only_index_paths_and_preserves_partial_staging(repo: Path):
    source = repo / "new file.py"
    source.write_text("staged content\n", encoding="utf-8")
    git(repo, "add", source.name)
    source.write_text("unstaged content\n", encoding="utf-8")
    (repo / "not-staged.py").write_text("local only\n", encoding="utf-8")
    assert update_inventory(repo, stage=True) == 0
    assert update_inventory(repo, check=True) == 0
    assert "new file.py" in inventory_paths(repo)
    assert "not-staged.py" not in inventory_paths(repo)
    assert git(repo, "show", ":new file.py") == b"staged content\n"
    assert source.read_text(encoding="utf-8") == "unstaged content\n"


@pytest.mark.parametrize("stage_manual_edit", [False, True])
def test_auto_stage_preserves_manual_inventory_metadata(repo: Path, stage_manual_edit: bool):
    (repo / "new.py").write_text("new\n", encoding="utf-8")
    git(repo, "add", "new.py")
    path = repo / "license-inventory.csv"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "existing.py,Elastic-2.0,2026 SuperTale contributors",
        "existing.py,MIT,Reviewed owner",
    ), encoding="utf-8")
    if stage_manual_edit:
        git(repo, "add", path.name)
    before = path.read_bytes()
    before_index = git(repo, "show", ":license-inventory.csv")
    assert update_inventory(repo, stage=True) == 1
    assert path.read_bytes() == before
    assert git(repo, "show", ":license-inventory.csv") == before_index


def test_auto_stage_handles_renames_and_removals(repo: Path):
    git(repo, "mv", "existing.py", "renamed.py")
    assert update_inventory(repo, stage=True) == 0
    assert "renamed.py" in inventory_paths(repo)
    assert "existing.py" not in inventory_paths(repo)
    git(repo, "rm", "--cached", "renamed.py")
    assert update_inventory(repo, stage=True) == 0
    assert "renamed.py" not in inventory_paths(repo)
    assert (repo / "renamed.py").is_file()


def test_auto_stage_preserves_unstaged_inventory_when_no_update_is_needed(repo: Path):
    path = repo / "license-inventory.csv"
    path.write_text("manual draft\n", encoding="utf-8")
    assert update_inventory(repo, stage=True) == 0
    assert path.read_text(encoding="utf-8") == "manual draft\n"


def test_auto_stage_rejects_deleted_inventory(repo: Path):
    git(repo, "rm", "--cached", "license-inventory.csv")
    before = (repo / "license-inventory.csv").read_bytes()
    assert update_inventory(repo, stage=True) == 1
    assert (repo / "license-inventory.csv").read_bytes() == before
    assert b"license-inventory.csv" not in git(repo, "ls-files", "-z").split(b"\0")
