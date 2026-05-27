"""
app/routes/items.py — CRUD для items + события
"""

import json
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db, Item, ItemEvent, Source, Tag, item_tags
from app.schemas import (
    ItemCreate, ItemUpdate, ItemPatch,
    ItemOut, ItemOutWithEvents, ItemEventOut,
)

router = APIRouter(prefix="/items", tags=["items"])


def _get_or_404(db: Session, uid: str) -> Item:
    item = db.get(Item, uid)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item '{uid}' не найден")
    return item


def _log_event(db: Session, item_uid: str, event_type: str, payload: dict):
    ev = ItemEvent(
        item_uid=item_uid,
        event_type=event_type,
        payload=json.dumps(payload, ensure_ascii=False),
    )
    db.add(ev)


#GET /items
@router.get("/", response_model=List[ItemOut], summary="Список items с фильтрацией")
def list_items(
    category: Optional[str] = Query(None, description="Фильтр по категории"),
    source:   Optional[str] = Query(None, description="Фильтр по источнику"),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    min_rating: Optional[int] = Query(None, ge=1, le=5),
    search:    Optional[str] = Query(None, description="Поиск по title"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Item)
    if category:
        q = q.filter(Item.category == category)
    if source:
        q = q.filter(Item.source == source)
    if min_price is not None:
        q = q.filter(Item.price >= min_price)
    if max_price is not None:
        q = q.filter(Item.price <= max_price)
    if min_rating is not None:
        q = q.filter(Item.rating >= min_rating)
    if search:
        q = q.filter(Item.title.ilike(f"%{search}%"))
    return q.offset(skip).limit(limit).all()


#GET /items/{uid} 
@router.get("/{uid}", response_model=ItemOutWithEvents, summary="Получить item по UID")
def get_item(uid: str, db: Session = Depends(get_db)):
    return _get_or_404(db, uid)


#POST /items
@router.post("/", response_model=ItemOut, status_code=201, summary="Создать item")
def create_item(data: ItemCreate, db: Session = Depends(get_db)):
    if db.get(Item, data.uid):
        raise HTTPException(status_code=400, detail=f"Item '{data.uid}' уже существует")

    now = datetime.utcnow().isoformat()
    item = Item(**data.model_dump(), loaded_at=now)
    db.add(item)
    _log_event(db, data.uid, "created", {"title": data.title})
    db.commit()
    db.refresh(item)
    return item


#PUT /items/{uid}
@router.put("/{uid}", response_model=ItemOut, summary="Полная замена item")
def replace_item(uid: str, data: ItemUpdate, db: Session = Depends(get_db)):
    item = _get_or_404(db, uid)
    old_price = item.price

    for field, val in data.model_dump().items():
        setattr(item, field, val)
    item.loaded_at = datetime.utcnow().isoformat()

    payload = {"action": "full_replace"}
    if old_price != data.price:
        payload["price_change"] = {"from": old_price, "to": data.price}

    _log_event(db, uid, "updated", payload)
    db.commit()
    db.refresh(item)
    return item


#PATCH /items/{uid}
@router.patch("/{uid}", response_model=ItemOut, summary="Частичное обновление item")
def patch_item(uid: str, data: ItemPatch, db: Session = Depends(get_db)):
    item = _get_or_404(db, uid)
    changes = {}

    for field, val in data.model_dump(exclude_unset=True).items():
        if getattr(item, field) != val:
            changes[field] = {"from": getattr(item, field), "to": val}
            setattr(item, field, val)

    item.loaded_at = datetime.utcnow().isoformat()
    if changes:
        _log_event(db, uid, "patched", changes)

    db.commit()
    db.refresh(item)
    return item


#DELETE /items/{uid}
@router.delete("/{uid}", status_code=204, summary="Удалить item")
def delete_item(uid: str, db: Session = Depends(get_db)):
    item = _get_or_404(db, uid)
    _log_event(db, uid, "deleted", {"title": item.title})
    db.delete(item)
    db.commit()


#GET /items/{uid}/events
@router.get("/{uid}/events", response_model=List[ItemEventOut], summary="История событий item")
def get_item_events(uid: str, db: Session = Depends(get_db)):
    _get_or_404(db, uid)
    return db.query(ItemEvent).filter(ItemEvent.item_uid == uid).order_by(ItemEvent.id.desc()).all()
