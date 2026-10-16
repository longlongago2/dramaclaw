from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from novelvideo.ports.local.project import AllowAllProjectAccess, SQLiteProjectRegistry


@pytest.fixture
def project_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from novelvideo import config, project_context
    from novelvideo.api.auth import get_api_user
    from novelvideo.api.routes import projects

    for key in ("OUTPUT_DIR", "STATE_DIR", "RUNTIME_DIR"):
        monkeypatch.setattr(config, key, str(tmp_path / key.lower()))
    registry = SQLiteProjectRegistry()
    access = AllowAllProjectAccess()
    for module in (projects, project_context):
        monkeypatch.setattr(module, "get_project_registry", lambda: registry)
        monkeypatch.setattr(module, "get_project_access", lambda: access)

    async def audit(**_kwargs):
        pass

    monkeypatch.setattr(projects, "emit_project_audit", audit)
    app = FastAPI()
    app.include_router(projects.router, prefix="/api/v1")
    app.dependency_overrides[get_api_user] = lambda: {
        "user_id": "local", "username": "alice", "role": "owner",
    }
    with TestClient(app) as client:
        yield client, registry, access, tmp_path


@pytest.mark.parametrize("title", ["火柴人", "../火柴人/第 1 集", "🎬" * 64])
def test_chinese_title_uses_ascii_directories_and_is_returned_by_all_read_apis(project_client, title):
    client, _, _, root = project_client
    response = client.post("/api/v1/projects", json={"display_name": f"  {title}  "})
    assert response.status_code == 200, response.text
    created = response.json()["data"]
    project_id = created["id"]
    assert created["name"] == f"p_{project_id}"
    assert created["display_name"] == title
    for directory in ("output_dir", "state_dir", "runtime_dir"):
        assert (root / directory / "alice" / created["name"]).is_dir()
        assert not (root / directory / "alice" / "火柴人").exists()
    for endpoint in ("/projects", "/projects/summaries"):
        row = client.get(f"/api/v1{endpoint}").json()["data"][0]
        assert row["id"] == project_id
        assert row["name"] == created["name"]
        assert row["display_name"] == title
    detail = client.get(f"/api/v1/projects/{project_id}").json()["data"]
    assert detail["name"] == created["name"]
    assert detail["display_name"] == title


def test_legacy_creation_and_rename_preserve_identity_paths_and_files(project_client):
    client, _, _, root = project_client
    created = client.post("/api/v1/projects", json={"name": "legacy"}).json()["data"]
    assert created["name"] == created["display_name"] == "legacy"
    markers = []
    for directory in ("output_dir", "state_dir", "runtime_dir"):
        marker = root / directory / "alice" / "legacy" / "keep.txt"
        marker.write_text("preserved", encoding="utf-8")
        markers.append(marker)
    endpoint = f"/api/v1/projects/{created['id']}/display-name"
    response = client.patch(endpoint, json={"display_name": "旧项目：火柴人"})
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "id": created["id"], "name": "legacy", "display_name": "旧项目：火柴人",
    }
    for marker in markers:
        assert marker.read_text(encoding="utf-8") == "preserved"
    detail = client.get(f"/api/v1/projects/{created['id']}").json()["data"]
    assert detail["name"] == "legacy"
    assert detail["display_name"] == "旧项目：火柴人"


def test_duplicate_title_conflicts_on_create_and_rename_without_partial_changes(project_client):
    client, _, _, _ = project_client
    first = client.post("/api/v1/projects", json={"display_name": "火柴人"}).json()["data"]
    second = client.post("/api/v1/projects", json={"name": "legacy"}).json()["data"]
    assert client.post("/api/v1/projects", json={"display_name": "火柴人"}).status_code == 409
    response = client.patch(
        f"/api/v1/projects/{second['id']}/display-name", json={"display_name": "火柴人"},
    )
    assert response.status_code == 409
    rows = client.get("/api/v1/projects").json()["data"]
    assert {row["id"]: row["display_name"] for row in rows} == {
        first["id"]: "火柴人", second["id"]: "legacy",
    }


@pytest.mark.parametrize("title", ["", "   ", "a" * 65, "a\nb", "a\x00b", "a\u2028b"])
def test_invalid_titles_are_rejected_before_creating_project_data(project_client, title):
    client, _, _, _ = project_client
    response = client.post("/api/v1/projects", json={"display_name": title})
    assert response.status_code == 422
    assert client.get("/api/v1/projects").json()["data"] == []


def test_rename_requires_admin_project_access(project_client, monkeypatch):
    client, _, access, _ = project_client
    created = client.post("/api/v1/projects", json={"name": "legacy"}).json()["data"]

    async def viewer(*_args):
        return "viewer"

    monkeypatch.setattr(access, "effective_project_role", viewer)
    response = client.patch(
        f"/api/v1/projects/{created['id']}/display-name", json={"display_name": "火柴人"},
    )
    assert response.status_code == 403
    assert client.get(f"/api/v1/projects/{created['id']}").json()["data"]["display_name"] == "legacy"


@pytest.mark.asyncio
async def test_old_registry_schema_is_migrated_without_changing_registered_paths(tmp_path, monkeypatch):
    from novelvideo import config

    monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))
    db_path = tmp_path / "local" / "projects.db"
    db_path.parent.mkdir()
    with sqlite3.connect(db_path) as db:
        db.execute("""CREATE TABLE projects (
            id TEXT PRIMARY KEY, owner_type TEXT, owner_id TEXT, owner_username TEXT,
            name TEXT, home_node_id TEXT, output_dir TEXT, state_dir TEXT, runtime_dir TEXT,
            status TEXT, created_at TEXT, updated_at TEXT, purged_at TEXT,
            UNIQUE(owner_type, owner_id, name)
        )""")
        db.execute("""INSERT INTO projects VALUES (
            'old-id', 'user', 'local', 'alice', 'legacy', 'local',
            '/original/output', '/original/state', '/original/runtime', 'active', '', '', NULL
        )""")
    for registry in (SQLiteProjectRegistry(), SQLiteProjectRegistry()):
        record = await registry.get_project("old-id")
        assert record.display_name == record.name == "legacy"
        assert (record.output_dir, record.state_dir, record.runtime_dir) == (
            "/original/output", "/original/state", "/original/runtime",
        )
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall() == [(1,), (2,)]


@pytest.mark.asyncio
async def test_legacy_registry_writes_keep_fallback_titles_unique(tmp_path, monkeypatch):
    from novelvideo import config

    monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))
    registry = SQLiteProjectRegistry()
    await registry.list_accessible_projects([("user", "local")])
    # A previous server version omits display_name when inserting a row.
    with sqlite3.connect(tmp_path / "local" / "projects.db") as db:
        db.execute(
            """INSERT INTO projects (
                id, owner_type, owner_id, owner_username, name, home_node_id,
                output_dir, state_dir, runtime_dir, status, created_at, updated_at
            ) VALUES (?, 'user', 'local', 'alice', ?, 'local', ?, ?, ?, 'active', '', '')""",
            (
                "old-writer-id", "legacy_writer",
                str(tmp_path / "output" / "alice" / "legacy_writer"),
                str(tmp_path / "state" / "alice" / "legacy_writer"),
                str(tmp_path / "runtime" / "alice" / "legacy_writer"),
            ),
        )
    assert (await registry.get_project("old-writer-id")).display_name == "legacy_writer"
    with pytest.raises(ValueError, match="already exists"):
        await registry.create_project(
            owner_user_id="local", owner_username="alice", display_name="legacy_writer",
        )


@pytest.mark.asyncio
async def test_concurrent_creation_normalizes_titles_and_enforces_uniqueness(tmp_path, monkeypatch):
    from novelvideo import config

    monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))
    registry = SQLiteProjectRegistry()
    results = await asyncio.gather(
        registry.create_project(owner_user_id="local", owner_username="alice", display_name="Café"),
        registry.create_project(owner_user_id="local", owner_username="alice", display_name="Cafe\u0301"),
        return_exceptions=True,
    )
    failures = [result for result in results if isinstance(result, Exception)]
    assert len(failures) == 1
    assert isinstance(failures[0], ValueError)
    assert "already exists" in str(failures[0])
    records = await registry.list_accessible_projects([("user", "local")])
    assert len(records) == 1
    assert records[0].display_name == "Café"
    for status in ("archived", "deleted"):
        await registry.update_project_status(records[0].id, status)
        with pytest.raises(ValueError, match="already exists"):
            await registry.create_project(owner_user_id="local", owner_username="alice", display_name="Café")
    await registry.mark_project_purged(records[0].id)
    replacement = await registry.create_project(owner_user_id="local", owner_username="alice", display_name="Café")
    assert replacement.id != records[0].id
