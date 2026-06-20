from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.features.notebooks.repository import NotebookRepository
from app.features.notebooks.service import NotebookService


def get_notebook_repository(
    db: AsyncSession = Depends(get_db),
) -> NotebookRepository:
    return NotebookRepository(db)


def get_notebook_service(
    repository: NotebookRepository = Depends(get_notebook_repository),
) -> NotebookService:
    return NotebookService(repository)
