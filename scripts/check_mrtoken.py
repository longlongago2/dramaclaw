"""Discover MrToken models using an environment-only platform credential."""

from __future__ import annotations

import asyncio
import argparse
import json
import os
import sys
from pathlib import Path

from novelvideo.mrtoken import discover_models


def main(argv: list[str] | None = None) -> int:
    """Query models before configuring mappings; never print the platform key."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, help="External JSON file with a key field")
    args = parser.parse_args(argv)
    api_key = os.environ.get("PLATFORM_API_KEY", "").strip()
    if args.key_file is not None:
        try:
            payload = json.loads(args.key_file.read_text(encoding="utf-8-sig"))
            value = payload.get("key") if isinstance(payload, dict) else None
            if not isinstance(value, str) or not value.strip():
                raise ValueError("missing key")
            api_key = value.strip()
        except (OSError, ValueError):
            print("Cannot read a valid key from the JSON file.", file=sys.stderr)
            return 2
    if not api_key:
        print("Set PLATFORM_API_KEY in the process environment first.", file=sys.stderr)
        return 2
    try:
        models = asyncio.run(discover_models(api_key))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Available models: {len(models)}")
    for model in models:
        print(model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
