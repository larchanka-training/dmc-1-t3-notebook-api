from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from app.features.notebooks.models import Notebook
from app.features.notebooks.repository import NotebookRepository
from app.features.notebooks.schemas import NotebookBlock, NotebookSnapshot
from app.features.notebooks.service import validate_snapshot


@dataclass(slots=True)
class NotebookAccessResult:
    status: Literal["missing", "forbidden", "owned"]
    notebook: Notebook | None = None


class AiRepository:
    def __init__(self, notebook_repository: NotebookRepository) -> None:
        self.notebook_repository = notebook_repository

    async def resolve_notebook_access(
        self, *, notebook_id: uuid.UUID, owner_id: uuid.UUID
    ) -> NotebookAccessResult:
        notebook = await self.notebook_repository.get_by_id(notebook_id)
        if notebook is None:
            return NotebookAccessResult(status="missing")
        if notebook.owner_id != owner_id:
            return NotebookAccessResult(status="forbidden", notebook=notebook)
        return NotebookAccessResult(status="owned", notebook=notebook)

    def parse_snapshot(self, notebook: Notebook) -> NotebookSnapshot:
        try:
            return validate_snapshot(notebook.content_snapshot)
        except ValidationError as exc:
            raise ValueError("Stored notebook snapshot is invalid.") from exc

    def find_block(
        self, snapshot: NotebookSnapshot, *, block_id: str
    ) -> NotebookBlock | None:
        for block in snapshot.blocks:
            if block.id == block_id:
                return block
        return None
