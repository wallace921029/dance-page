import pytest
from sqlalchemy import select

from app.models import Favorite
from tests.conftest import create_invite, register


@pytest.fixture
def other_reader(admin, new_client):
    c = new_client()
    assert register(c, create_invite(admin)["code"], "xiaohong").status_code == 201
    return c


def shelf_entry(client, book_id):
    [entry] = [b for b in client.get("/api/books").json() if b["id"] == book_id]
    return entry


def test_shelf_reports_favorite_state_and_cover_aspect(reader, ready_book):
    entry = shelf_entry(reader, ready_book["id"])
    assert entry["is_favorite"] is False
    assert entry["favorited_at"] is None
    page = ready_book["pages"][0]
    assert entry["cover_aspect"] == pytest.approx(page["width"] / page["height"])


def test_add_and_remove_favorite(reader, ready_book):
    book_id = ready_book["id"]
    assert reader.put(f"/api/books/{book_id}/favorite").status_code == 204
    # 重复收藏没有副作用
    assert reader.put(f"/api/books/{book_id}/favorite").status_code == 204
    entry = shelf_entry(reader, book_id)
    assert entry["is_favorite"] is True
    assert entry["favorited_at"] is not None
    assert reader.get(f"/api/books/{book_id}").json()["is_favorite"] is True

    assert reader.delete(f"/api/books/{book_id}/favorite").status_code == 204
    assert reader.delete(f"/api/books/{book_id}/favorite").status_code == 204
    assert shelf_entry(reader, book_id)["is_favorite"] is False


def test_favorites_are_per_user(reader, other_reader, ready_book):
    reader.put(f"/api/books/{ready_book['id']}/favorite")
    assert shelf_entry(reader, ready_book["id"])["is_favorite"] is True
    assert shelf_entry(other_reader, ready_book["id"])["is_favorite"] is False


def test_cannot_favorite_unlisted_book_but_can_remove(admin, reader, ready_book):
    book_id = ready_book["id"]
    reader.put(f"/api/books/{book_id}/favorite")
    admin.patch(f"/api/admin/books/{book_id}", json={"visibility": "unlisted"})
    assert reader.put(f"/api/books/{book_id}/favorite").status_code == 404
    assert reader.delete(f"/api/books/{book_id}/favorite").status_code == 204


def test_unknown_book(reader):
    assert reader.put("/api/books/nope/favorite").status_code == 404


def test_favorite_requires_login(client, ready_book):
    assert client.put(f"/api/books/{ready_book['id']}/favorite").status_code == 401


def test_deleting_book_removes_favorites(admin, reader, ready_book, app):
    reader.put(f"/api/books/{ready_book['id']}/favorite")
    admin.delete(f"/api/admin/books/{ready_book['id']}")
    with app.state.session_factory() as db:
        assert db.scalars(select(Favorite)).all() == []
