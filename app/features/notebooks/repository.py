from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.notebooks.models import Notebook


class NotebookRepository:
    """Data-access primitives for owner-scoped notebook rows."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        owner_id: uuid.UUID,
        title: str,
        content_snapshot: dict[str, Any],
        revision: int = 1,
    ) -> Notebook:
        notebook = Notebook(
            owner_id=owner_id,
            title=title,
            content_snapshot=content_snapshot,
            revision=revision,
        )
        self.session.add(notebook)
        await self.session.flush()
        return notebook

    async def get_by_id(self, notebook_id: uuid.UUID) -> Notebook | None:
        return await self.session.get(Notebook, notebook_id)

    async def get_owned(
        self, *, notebook_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Notebook | None:
        notebook = await self.session.get(Notebook, notebook_id)
        if notebook is None or notebook.owner_id != owner_id:
            return None
        return notebook

    async def list_for_owner(self, owner_id: uuid.UUID) -> list[Notebook]:
        stmt = (
            select(Notebook)
            .where(Notebook.owner_id == owner_id)
            .order_by(Notebook.updated_at.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result)

    async def update(
        self,
        notebook: Notebook,
        *,
        title: str | None = None,
        content_snapshot: dict[str, Any] | None = None,
        revision: int | None = None,
        last_synced_at: datetime | None = None,
    ) -> Notebook:
        if title is not None:
            notebook.title = title
        if content_snapshot is not None:
            notebook.content_snapshot = content_snapshot
        if revision is not None:
            notebook.revision = revision
        if last_synced_at is not None:
            notebook.last_synced_at = last_synced_at
        await self.session.flush()
        return notebook

    async def delete(self, notebook: Notebook) -> None:
        await self.session.delete(notebook)
        await self.session.flush()
