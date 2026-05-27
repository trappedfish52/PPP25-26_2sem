"""
app/routes/sources.py — CRUD для sources
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db, Source
from app.schemas import SourceCreate, SourceUpdate, SourcePatch, SourceOut

router = APIRouter(prefix="/sources", tags=["sources"])


def _get_or_404(db: Session, source_id: int) -> Source:
    src = db.get(Source, source_id)
    if not src:
        raise HTTPException(status_code=404, detail=f"Source {source_id} не найден")
    return src


# ── GET /sources ───────────────────────────────────────────────────────────────
@router.get("/", response_model=List[SourceOut], summary="Список источников")
def list_sources(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    q = db.query(Source)
    if active_only:
        q = q.filter(Source.is_active == True)
    return q.all()


# ── GET /sources/{id} ─────────────────────────────────────────────────────────
@router.get("/{source_id}", response_model=SourceOut, summary="Источник по ID")
def get_source(source_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, source_id)


# ── POST /sources ──────────────────────────────────────────────────────────────
@router.post("/", response_model=SourceOut, status_code=201, summary="Создать источник")
def create_source(data: SourceCreate, db: Session = Depends(get_db)):
    existing = db.query(Source).filter(Source.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Source '{data.name}' уже существует")
    src = Source(**data.model_dump())
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


# ── PUT /sources/{id} ─────────────────────────────────────────────────────────
@router.put("/{source_id}", response_model=SourceOut, summary="Полная замена источника")
def replace_source(source_id: int, data: SourceUpdate, db: Session = Depends(get_db)):
    src = _get_or_404(db, source_id)
    # проверяем уникальность имени
    conflict = db.query(Source).filter(Source.name == data.name, Source.id != source_id).first()
    if conflict:
        raise HTTPException(status_code=400, detail=f"Имя '{data.name}' занято другим источником")
    for field, val in data.model_dump().items():
        setattr(src, field, val)
    db.commit()
    db.refresh(src)
    return src


# ── PATCH /sources/{id} ───────────────────────────────────────────────────────
@router.patch("/{source_id}", response_model=SourceOut, summary="Частичное обновление источника")
def patch_source(source_id: int, data: SourcePatch, db: Session = Depends(get_db)):
    src = _get_or_404(db, source_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(src, field, val)
    db.commit()
    db.refresh(src)
    return src


# ── DELETE /sources/{id} ──────────────────────────────────────────────────────
@router.delete("/{source_id}", status_code=204, summary="Удалить источник")
def delete_source(source_id: int, db: Session = Depends(get_db)):
    src = _get_or_404(db, source_id)
    db.delete(src)
    db.commit()
