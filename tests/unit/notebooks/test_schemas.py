from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.features.notebooks.schemas import (
    NotebookCreateRequest,
    NotebookPatchRequest,
    NotebookSnapshot,
)


def _snapshot(**overrides) -> dict:
    base = {
        "id": "nb-1",
        "title": "T",
        "tags": ["reference"],
        "blocks": [
            {
                "id": "b1",
                "type": "text",
                "content": {"markdown": "# Hi"},
                "meta": {"tags": ["intro"]},
            },
            {
                "id": "b2",
                "type": "code",
                "content": {"language": "javascript", "source": "1 + 1"},
                "meta": {"tags": ["ex"]},
            },
        ],
        "metadata": {"version": 1},
    }
    base.update(overrides)
    return base


def test_valid_snapshot_parses_and_preserves_order_and_tags() -> None:
    snapshot = NotebookSnapshot.model_validate(_snapshot())
    assert [b.id for b in snapshot.blocks] == ["b1", "b2"]
    assert snapshot.tags == ["reference"]
    assert snapshot.blocks[0].meta.tags == ["intro"]


def test_notebook_tags_default_to_empty_list() -> None:
    data = _snapshot()
    del data["tags"]
    snapshot = NotebookSnapshot.model_validate(data)
    assert snapshot.tags == []


def test_block_meta_tags_default_to_empty_list_when_absent() -> None:
    data = _snapshot(
        blocks=[{"id": "b1", "type": "text", "content": {"markdown": "x"}}]
    )
    snapshot = NotebookSnapshot.model_validate(data)
    assert snapshot.blocks[0].meta.tags == []


def test_rejects_unknown_block_type() -> None:
    data = _snapshot(
        blocks=[{"id": "b1", "type": "image", "content": {}, "meta": {"tags": []}}]
    )
    with pytest.raises(ValidationError):
        NotebookSnapshot.model_validate(data)


def test_rejects_non_javascript_code_block() -> None:
    data = _snapshot(
        blocks=[
            {
                "id": "b1",
                "type": "code",
                "content": {"language": "python", "source": "x=1"},
                "meta": {"tags": []},
            }
        ]
    )
    with pytest.raises(ValidationError):
        NotebookSnapshot.model_validate(data)


def test_rejects_runtime_output_on_block() -> None:
    data = _snapshot(
        blocks=[
            {
                "id": "b1",
                "type": "text",
                "content": {"markdown": "x"},
                "meta": {"tags": []},
                "output": {"kind": "text", "value": "leak"},
            }
        ]
    )
    with pytest.raises(ValidationError):
        NotebookSnapshot.model_validate(data)


def test_create_request_requires_title_and_snapshot() -> None:
    with pytest.raises(ValidationError):
        NotebookCreateRequest.model_validate({"title": "T"})


def test_patch_request_allows_optional_title() -> None:
    assert NotebookPatchRequest.model_validate({}).title is None
    assert NotebookPatchRequest.model_validate({"title": "R"}).title == "R"
