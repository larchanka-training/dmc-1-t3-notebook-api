from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class BlockMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tags: list[str] = Field(default_factory=list)


class TextBlockContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    markdown: str


class CodeBlockContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["javascript"]
    source: str


class TextBlock(BaseModel):
    # extra="forbid" excludes runtime outputs from the durable snapshot.
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["text"]
    content: TextBlockContent
    meta: BlockMeta = Field(default_factory=BlockMeta)


class CodeBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["code"]
    content: CodeBlockContent
    meta: BlockMeta = Field(default_factory=BlockMeta)


NotebookBlock = Annotated[
    Union[TextBlock, CodeBlock], Field(discriminator="type")
]


class NotebookSnapshot(BaseModel):
    """Canonical Version 1 notebook document stored as `content_snapshot`."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    title: str
    tags: list[str] = Field(default_factory=list)
    blocks: list[NotebookBlock] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=lambda: {"version": 1})


class NotebookCreateRequest(BaseModel):
    title: str
    content_snapshot: NotebookSnapshot


class NotebookSyncRequest(BaseModel):
    base_revision: int
    content_snapshot: NotebookSnapshot


class NotebookPatchRequest(BaseModel):
    title: str | None = None


class NotebookSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    tags: list[str] = Field(default_factory=list)
    revision: int
    created_at: datetime
    updated_at: datetime


class NotebookResponse(BaseModel):
    id: uuid.UUID
    title: str
    tags: list[str] = Field(default_factory=list)
    blocks: list[NotebookBlock] = Field(default_factory=list)
    revision: int
    created_at: datetime
    updated_at: datetime
    last_synced_at: datetime | None = None


class ErrorResponse(BaseModel):
    detail: str


class SyncConflictErrorBody(BaseModel):
    code: str
    message: str


class NotebookSyncConflictResponse(BaseModel):
    error: SyncConflictErrorBody
    server_revision: int
