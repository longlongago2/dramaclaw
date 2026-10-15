# SPDX-License-Identifier: Elastic-2.0
# Copyright (c) 2026 ClaymoreLab
"""Task-local, submission-time style snapshots, also inherited by model children."""

import json
import os
from contextlib import contextmanager
from contextvars import ContextVar

STYLE_SNAPSHOT_ENV = "DRAMACLAW_STYLE_SNAPSHOT"
_snapshot: ContextVar[dict | None] = ContextVar("style_snapshot", default=None)


def active_style_snapshot() -> dict | None:
    current = _snapshot.get()
    if current is not None:
        return current
    raw = os.environ.get(STYLE_SNAPSHOT_ENV)
    if not raw:
        return None
    return json.loads(raw)


@contextmanager
def style_snapshot_scope(snapshot: dict | None):
    token = _snapshot.set(snapshot)
    try:
        yield
    finally:
        _snapshot.reset(token)


def capture_project_style(ctx) -> dict | None:
    from novelvideo.project_config import load_project_config_file_from_state_dir
    from novelvideo.services.style_service import StyleService
    from novelvideo.styles.stickman import RULES_VERSION

    inherited = active_style_snapshot()
    project_id = str(getattr(ctx, "project_id", ""))
    if inherited and inherited.get("id") and inherited.get("project_id", "") == project_id:
        return dict(inherited)
    config = load_project_config_file_from_state_dir(ctx.state_dir)
    style = StyleService.get_style(
        str(config.get("visual_style") or "chinese_period_drama"),
        state_dir=ctx.state_dir, project_dir=ctx.output_dir,
    )
    if style is None or style.character_representation != "stick_figure":
        return None
    return {**style.model_dump(mode="json"), "rules_version": RULES_VERSION, "project_id": project_id}
