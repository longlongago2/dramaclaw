"""Project DTOs and access ports."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException

PROJECT_ROLE_VIEWER = "viewer"
PROJECT_ROLE_EDITOR = "editor"
PROJECT_ROLE_ADMIN = "admin"
PROJECT_ROLE_OWNER = "owner"

ROLE_ORDER = {
    PROJECT_ROLE_VIEWER: 10,
    PROJECT_ROLE_EDITOR: 20,
    PROJECT_ROLE_ADMIN: 30,
    PROJECT_ROLE_OWNER: 40,
}


def normalize_project_display_name(value: str) -> str:
    """Normalize a single-line, user-facing title without using it as a path."""
    name = unicodedata.normalize("NFC", value).strip()
    if not name or len(name) > 64:
        raise ValueError("Project display name must be between 1 and 64 characters long")
    if any(unicodedata.category(char) in {"Cc", "Cs", "Zl", "Zp"} for char in name):
        raise ValueError("Project display name must not contain control characters or line breaks")
    return name


@dataclass(frozen=True)
class ProjectRecord:
    id: str
    owner_type: str
    owner_id: str
    owner_username: str
    name: str
    home_node_id: str
    output_dir: str
    state_dir: str
    runtime_dir: str
    status: str
    created_at: str = ""
    updated_at: str = ""
    purged_at: str | None = None
    storage_org_id: str | None = None
    storage_org_name: str | None = None
    display_name: str = ""


@dataclass(frozen=True)
class Principal:
    type: str
    id: str


def role_allows(actual: str, required: str) -> bool:
    return ROLE_ORDER.get(actual, 0) >= ROLE_ORDER.get(required, 0)


def require_role_value(actual: str | None, required: str) -> None:
    if not actual or not role_allows(actual, required):
        raise HTTPException(status_code=403, detail=f"project role required: {required}")


class ProjectRegistry(Protocol):
    async def get_project(self, project_id: str) -> ProjectRecord | None: ...

    async def get_project_by_owner_name(
        self,
        owner_user_id: str,
        name: str,
    ) -> ProjectRecord | None: ...

    async def create_project(
        self,
        *,
        owner_user_id: str,
        owner_username: str,
        name: str | None = None,
        display_name: str | None = None,
        home_node_id: str | None = None,
        output_dir: str | None = None,
        state_dir: str | None = None,
        runtime_dir: str | None = None,
    ) -> ProjectRecord: ...

    async def update_project_display_name(
        self,
        project_id: str,
        display_name: str,
    ) -> ProjectRecord | None: ...

    async def list_accessible_projects(
        self,
        principals: list[tuple[str, str]],
    ) -> list[ProjectRecord]: ...

    async def update_project_status(
        self,
        project_id: str,
        status: str,
    ) -> ProjectRecord | None: ...

    async def mark_project_purged(self, project_id: str) -> ProjectRecord | None: ...

    async def delete_uncommitted_project(self, project_id: str) -> None: ...

    async def delete_project_home(self, project_id: str) -> None: ...

    async def resolve_username_by_user_id(self, user_id: str) -> str | None: ...

    async def resolve_user_id_by_username(self, username: str) -> str | None: ...


class ProjectAccess(Protocol):
    """Authoritative project authorization.

    Providers may additionally expose ``effective_media_read_role(project,
    principals)`` returning only viewer/None. Media handlers opt into that
    optional cached capability; older providers fall back to the methods here.
    It must never be used to authorize mutations or background work.
    """

    async def resolve_requester_principals(self, user_id: str) -> list[Principal]: ...

    async def effective_project_role(
        self,
        project: ProjectRecord,
        principals: list[Principal],
    ) -> str | None: ...

    async def effective_project_role_by_id(
        self,
        project_id: str,
        principals: list[Principal],
    ) -> str | None: ...

    async def count_project_task_eligible_users(
        self,
        *,
        project_id: str,
        owner_type: str,
        owner_id: str,
    ) -> int: ...
