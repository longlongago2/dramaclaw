# SPDX-License-Identifier: Elastic-2.0
# SPDX-FileCopyrightText: 2026 SuperTale contributors
"""Update only the license inventory, using paths in Git's current index."""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path
import subprocess
import sys

from scripts.compliance.generate_p0b_artifacts import render_license_inventory


def update_inventory(root: Path, *, check: bool = False) -> int:
    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", "-C", str(root), *args])

    inventory_path = root / "license-inventory.csv"
    files = [item.decode("utf-8") for item in git("ls-files", "-z").split(b"\0") if item]
    if git("ls-files", "--unmerged", "-z"):
        print("Resolve merge conflicts before updating the license inventory.", file=sys.stderr)
        return 1

    expected = render_license_inventory(files).replace("\r\n", "\n")
    staged = git("show", ":license-inventory.csv").decode("utf-8").replace("\r\n", "\n") if "license-inventory.csv" in files else ""
    # pre-commit hides unstaged changes before running hooks. Never write here:
    # an auto-fix can conflict with the hidden inventory when it is restored.
    if check:
        if staged == expected:
            return 0
        print(
            "The staged license inventory is out of date. Run "
            "python -X utf8 -m scripts.compliance.update_license_inventory, "
            "then git add license-inventory.csv and retry the commit.",
            file=sys.stderr,
        )
        return 1

    current = inventory_path.read_text(encoding="utf-8") if inventory_path.exists() else ""
    if current == expected:
        if "license-inventory.csv" not in files:
            print("Stage license-inventory.csv before committing: git add license-inventory.csv")
            return 1
        return 0

    if current != staged:
        print(
            "license-inventory.csv has unstaged edits; preserved without overwriting. "
            "Review and stage those edits before retrying.",
            file=sys.stderr,
        )
        return 1

    # Preserve explicitly reviewed metadata, even if it has already been staged.
    # Such changes belong in the generator's path overrides before regeneration.
    try:
        old_rows = {row["path"]: row for row in csv.DictReader(io.StringIO(current))}
        new_rows = {row["path"]: row for row in csv.DictReader(io.StringIO(expected))}
    except (KeyError, csv.Error):
        print("Invalid license inventory; repair it before retrying.", file=sys.stderr)
        return 1
    conflicts = sorted(path for path in old_rows.keys() & new_rows.keys() if old_rows[path] != new_rows[path])
    if conflicts:
        print(
            "License metadata differs from the generator for: " + ", ".join(conflicts)
            + ". Preserved existing metadata; update generator overrides first.",
            file=sys.stderr,
        )
        return 1

    inventory_path.write_bytes(expected.encode("utf-8"))
    print("Updated license-inventory.csv from the Git index. Run git add license-inventory.csv, then retry the commit.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check the Git index without modifying files.")
    args = parser.parse_args()
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    return update_inventory(root, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
