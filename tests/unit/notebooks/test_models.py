from __future__ import annotations

from app.features.notebooks.models import Notebook


def test_notebook_table_name() -> None:
    assert Notebook.__tablename__ == "notebooks"


def test_notebook_has_expected_columns() -> None:
    columns = set(Notebook.__table__.columns.keys())
    expected = {
        "id",
        "owner_id",
        "title",
        "content_snapshot",
        "revision",
        "created_at",
        "updated_at",
        "last_synced_at",
    }
    assert expected <= columns


def test_owner_id_is_foreign_key_to_users() -> None:
    foreign_keys = list(Notebook.__table__.c.owner_id.foreign_keys)
    assert any(fk.target_fullname == "users.id" for fk in foreign_keys)


def test_nullability_and_required_fields() -> None:
    columns = Notebook.__table__.columns
    assert columns["last_synced_at"].nullable is True
    assert columns["revision"].nullable is False
    assert columns["content_snapshot"].nullable is False
    assert columns["title"].nullable is False
