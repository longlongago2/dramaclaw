#!/usr/bin/env python3
"""Build and publish the three local Compose images to the company Harbor.

Run from any directory; Docker commands use the repository root. Credentials
are entered directly into Docker's interactive login prompt, never this script.
See scripts/publish_harbor.md for usage and deployment instructions.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REGISTRY = "harbor.n.nebulaedata.com"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
IMAGES = (
    ("dramaclaw-local/api:latest", "dramaclaw"),
    ("dramaclaw-local/gateway:latest", "dramaclaw-gateway"),
    ("dramaclaw-local/web:latest", "dramaclaw-frontend"),
)


def project_name(value: str) -> str:
    """Accept a single lowercase Harbor project name, not a registry path."""
    if not re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", value):
        raise argparse.ArgumentTypeError(
            "project must be lowercase letters/digits separated by '.', '_' or '-'"
        )
    return value


def image_tag(value: str) -> str:
    """Validate a Docker tag before any login, build or push."""
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", value):
        raise argparse.ArgumentTypeError(
            "tag must be 1-128 letters/digits/underscores/dots/hyphens, "
            "and cannot start with '.' or '-'"
        )
    return value


def run_docker(arguments: list[str], *, dry_run: bool) -> None:
    """Run without a shell, inherit the terminal, and stop on Docker failure."""
    print("+ docker " + " ".join(arguments), flush=True)
    if not dry_run:
        subprocess.run(["docker", *arguments], cwd=REPOSITORY_ROOT, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        type=project_name,
        default="dramaclaw",
        help="existing Harbor project (default: dramaclaw)",
    )
    parser.add_argument(
        "--tag", type=image_tag, help="image tag (default: local time YYYYMMDD-HHMMSS)"
    )
    parser.add_argument(
        "--username", help="Harbor username; Docker prompts for password"
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="publish existing local images without rebuilding",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print commands without login, build, tag or push",
    )
    args = parser.parse_args(argv)
    tag = args.tag or datetime.now().strftime("%Y%m%d-%H%M%S")
    prefix = f"{REGISTRY}/{args.project}"

    if not args.dry_run and shutil.which("docker") is None:
        print("Docker CLI was not found on PATH.", file=sys.stderr)
        return 1

    print(f"Publishing to {prefix}, tag: {tag}")
    if args.dry_run:
        print("Dry run: no Docker commands will be executed.")
    try:
        # Quiet validation avoids printing values from the runtime .env file.
        run_docker(
            ["compose", "-f", "docker-compose.yml", "config", "--quiet"],
            dry_run=args.dry_run,
        )
        login = ["login", REGISTRY]
        if args.username:
            login.extend(["--username", args.username])
        run_docker(login, dry_run=args.dry_run)
        if not args.skip_build:
            run_docker(
                [
                    "compose",
                    "-f",
                    "docker-compose.yml",
                    "build",
                    "api",
                    "newapi",
                    "web",
                ],
                dry_run=args.dry_run,
            )

        # Check all three sources before pushing any image.
        run_docker(
            [
                "image",
                "inspect",
                "--format",
                "{{.Id}}",
                *(source for source, _ in IMAGES),
            ],
            dry_run=args.dry_run,
        )
        for source, repository in IMAGES:
            run_docker(
                ["tag", source, f"{prefix}/{repository}:{tag}"], dry_run=args.dry_run
            )
        for _, repository in IMAGES:
            run_docker(["push", f"{prefix}/{repository}:{tag}"], dry_run=args.dry_run)
    except subprocess.CalledProcessError as exc:
        print(
            f"Docker failed (exit {exc.returncode}); publication stopped. "
            "Any earlier successful pushes remain in Harbor.",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        print(f"Could not run Docker: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Publication interrupted.", file=sys.stderr)
        return 130

    print("\n" + ("Preview complete." if args.dry_run else "Publication complete."))
    print("Set these values in the deployment server's .env:")
    print(f"DRAMACLAW_IMAGE_PREFIX={prefix}")
    print(f"DRAMACLAW_VERSION={tag}")
    print(f"DRAMACLAW_GATEWAY_VERSION={tag}")
    print("docker compose -f docker-compose.release.yml pull")
    print("docker compose -f docker-compose.release.yml up -d")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
