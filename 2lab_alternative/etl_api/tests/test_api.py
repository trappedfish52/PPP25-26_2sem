"""
tests/test_api.py — юнит/интеграционные тесты без запуска Uvicorn

Запуск:
    pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app

# ── In-memory SQLite для тестов ───────────────────────────────────────────────
TEST_DB_URL = "sqlite://"   # чистая in-memory база

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """пересоздаём таблицы перед каждым тестом"""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


#SOURCES

def test_list_sources_empty():
    """GET /sources — пустой список при старте."""
    response = client.get("/sources/")
    assert response.status_code == 200
    assert response.json() == []


def test_create_source():
    """POST /sources — создание источника."""
    payload = {"name": "test.source.com", "url": "https://test.source.com", "category": "test", "is_active": True}
    response = client.post("/sources/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test.source.com"
    assert data["id"] == 1


def test_create_source_duplicate():
    """POST /sources — дубликат → 400."""
    payload = {"name": "dup.com", "url": None, "category": "x", "is_active": True}
    client.post("/sources/", json=payload)
    response = client.post("/sources/", json=payload)
    assert response.status_code == 400


def test_get_source_by_id():
    """GET /sources/{id}."""
    client.post("/sources/", json={"name": "s1.com", "url": None, "category": "book", "is_active": True})
    response = client.get("/sources/1")
    assert response.status_code == 200
    assert response.json()["name"] == "s1.com"


def test_get_source_not_found():
    """GET /sources/999 → 404."""
    response = client.get("/sources/999")
    assert response.status_code == 404


def test_put_source():
    """PUT /sources/{id} — полная замена."""
    client.post("/sources/", json={"name": "old.com", "url": None, "category": "book", "is_active": True})
    response = client.put("/sources/1", json={"name": "new.com", "url": "https://new.com", "category": "quote", "is_active": False})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "new.com"
    assert data["is_active"] is False


def test_patch_source():
    """PATCH /sources/{id} — частичное обновление."""
    client.post("/sources/", json={"name": "patch.com", "url": None, "category": "book", "is_active": True})
    response = client.patch("/sources/1", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_delete_source():
    """DELETE /sources/{id}."""
    client.post("/sources/", json={"name": "del.com", "url": None, "category": "book", "is_active": True})
    response = client.delete("/sources/1")
    assert response.status_code == 204
    assert client.get("/sources/1").status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# ITEMS
# ═══════════════════════════════════════════════════════════════════════════════

ITEM_PAYLOAD = {
    "uid": "abc123def456",
    "source": "books.toscrape.com",
    "category": "book",
    "title": "The Great Gatsby",
    "price": 9.99,
    "rating": 4,
    "description": "A classic novel",
    "tags": "fiction, classic",
    "scraped_at": "2024-01-01T00:00:00",
}


def test_list_items_empty():
    """GET /items/ — пустой список."""
    response = client.get("/items/")
    assert response.status_code == 200
    assert response.json() == []


def test_create_item():
    """POST /items/ — создание item."""
    response = client.post("/items/", json=ITEM_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["uid"] == "abc123def456"
    assert data["title"] == "The Great Gatsby"


def test_create_item_duplicate():
    """POST /items/ — дубликат → 400."""
    client.post("/items/", json=ITEM_PAYLOAD)
    response = client.post("/items/", json=ITEM_PAYLOAD)
    assert response.status_code == 400


def test_get_item_by_uid():
    """GET /items/{uid}."""
    client.post("/items/", json=ITEM_PAYLOAD)
    response = client.get("/items/abc123def456")
    assert response.status_code == 200
    assert response.json()["uid"] == "abc123def456"


def test_get_item_not_found():
    """GET /items/nonexistent → 404."""
    response = client.get("/items/nonexistent")
    assert response.status_code == 404


def test_put_item():
    """PUT /items/{uid} — полная замена."""
    client.post("/items/", json=ITEM_PAYLOAD)
    updated = {**ITEM_PAYLOAD, "title": "Updated Title", "price": 19.99}
    response = client.put("/items/abc123def456", json=updated)
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"
    assert response.json()["price"] == 19.99


def test_patch_item():
    """PATCH /items/{uid} — частичное обновление."""
    client.post("/items/", json=ITEM_PAYLOAD)
    response = client.patch("/items/abc123def456", json={"price": 5.55, "rating": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["price"] == 5.55
    assert data["rating"] == 3
    assert data["title"] == "The Great Gatsby"  # не изменился


def test_patch_item_invalid_rating():
    """PATCH /items/{uid} — невалидный rating → 422."""
    client.post("/items/", json=ITEM_PAYLOAD)
    response = client.patch("/items/abc123def456", json={"rating": 10})
    assert response.status_code == 422


def test_delete_item():
    """DELETE /items/{uid}."""
    client.post("/items/", json=ITEM_PAYLOAD)
    response = client.delete("/items/abc123def456")
    assert response.status_code == 204
    assert client.get("/items/abc123def456").status_code == 404


def test_list_items_filter_category():
    """GET /items/?category=book — фильтрация."""
    client.post("/items/", json=ITEM_PAYLOAD)
    quote_payload = {**ITEM_PAYLOAD, "uid": "qqqqq1111111", "category": "quote", "price": None, "rating": None}
    client.post("/items/", json=quote_payload)

    response = client.get("/items/?category=book")
    data = response.json()
    assert len(data) == 1
    assert data[0]["category"] == "book"


def test_list_items_search():
    """GET /items/?search=Gatsby — поиск по title."""
    client.post("/items/", json=ITEM_PAYLOAD)
    response = client.get("/items/?search=Gatsby")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_item_events_after_create():
    """GET /items/{uid}/events — событие 'created' должно быть после создания."""
    client.post("/items/", json=ITEM_PAYLOAD)
    response = client.get("/items/abc123def456/events")
    assert response.status_code == 200
    events = response.json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "created"


def test_item_events_after_patch():
    """Патч item → добавляет событие 'patched'."""
    client.post("/items/", json=ITEM_PAYLOAD)
    client.patch("/items/abc123def456", json={"price": 1.00})
    response = client.get("/items/abc123def456/events")
    event_types = [e["event_type"] for e in response.json()]
    assert "patched" in event_types


# ═══════════════════════════════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════════════════════════════

def test_stats_empty():
    """GET /stats/ — нули при пустой БД."""
    response = client.get("/stats/")
    assert response.status_code == 200
    data = response.json()
    assert data["total_items"] == 0
    assert data["total_sources"] == 0


def test_stats_with_data():
    """GET /stats/ — корректные данные после наполнения."""
    client.post("/sources/", json={"name": "s.com", "url": None, "category": "book", "is_active": True})
    client.post("/items/", json=ITEM_PAYLOAD)
    response = client.get("/stats/")
    data = response.json()
    assert data["total_items"] == 1
    assert data["total_sources"] == 1
    assert "book" in data["by_category"]


# ═══════════════════════════════════════════════════════════════════════════════
# TASKS (без Redis — ожидаем 503)


def test_start_rebuild_stats_no_redis():
    """POST /tasks/rebuild_stats — 503 если Redis недоступен."""
    response = client.post("/tasks/rebuild_stats")
    # Если Redis есть — ожидаем 202; если нет — 503
    assert response.status_code in (202, 503)


def test_get_task_status_no_redis():
    """GET /tasks/{task_id} — 503 если Redis недоступен."""
    response = client.get("/tasks/fake-task-id-000")
    assert response.status_code in (200, 503)
