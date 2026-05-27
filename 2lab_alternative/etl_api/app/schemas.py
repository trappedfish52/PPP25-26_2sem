"""
app/schemas.py — Pydantic-схемы для валидации входных/выходных данных
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# ═══════════════════════════════ SOURCE ════════════════════════════════════════

class SourceBase(BaseModel):
    name:      str = Field(..., max_length=120)
    url:       Optional[str] = Field(None, max_length=255)
    category:  Optional[str] = Field(None, max_length=60)
    is_active: bool = True


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    """PUT — полная замена"""
    name:      str
    url:       Optional[str] = None
    category:  Optional[str] = None
    is_active: bool = True


class SourcePatch(BaseModel):
    """PATCH — частичное обновление"""
    name:      Optional[str] = None
    url:       Optional[str] = None
    category:  Optional[str] = None
    is_active: Optional[bool] = None


class SourceOut(SourceBase):
    model_config = ConfigDict(from_attributes=True)
    id:         int
    created_at: Optional[datetime] = None


# ═══════════════════════════════ TAG ═══════════════════════════════════════════

class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:   int
    name: str


# ═══════════════════════════════ ITEM_EVENT ════════════════════════════════════

class ItemEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:         int
    item_uid:   str
    event_type: str
    payload:    Optional[str] = None
    created_at: Optional[datetime] = None


# ═══════════════════════════════ ITEM ══════════════════════════════════════════

class ItemBase(BaseModel):
    uid:         str = Field(..., max_length=12)
    source:      Optional[str] = None
    category:    str
    title:       str
    price:       Optional[float] = None
    rating:      Optional[int]   = Field(None, ge=1, le=5)
    description: Optional[str]   = None
    tags:        Optional[str]   = None


class ItemCreate(ItemBase):
    scraped_at: Optional[str] = None


class ItemUpdate(ItemBase):
    """PUT — полная замена"""
    scraped_at: Optional[str] = None


class ItemPatch(BaseModel):
    """PATCH — частичное обновление"""
    source:      Optional[str]   = None
    category:    Optional[str]   = None
    title:       Optional[str]   = None
    price:       Optional[float] = None
    rating:      Optional[int]   = Field(None, ge=1, le=5)
    description: Optional[str]   = None
    tags:        Optional[str]   = None


class ItemOut(ItemBase):
    model_config = ConfigDict(from_attributes=True)
    scraped_at:  Optional[str] = None
    loaded_at:   Optional[str] = None
    tag_rels:    List[TagOut]  = []


class ItemOutWithEvents(ItemOut):
    events: List[ItemEventOut] = []


# ═══════════════════════════════ STATS ═════════════════════════════════════════

class StatsOut(BaseModel):
    total_items:   int
    total_sources: int
    by_category:   dict
    avg_price:     Optional[float]
    avg_rating:    Optional[float]


# ═══════════════════════════════ TASK (Celery) ═════════════════════════════════

class TaskOut(BaseModel):
    task_id: str
    status:  str
    result:  Optional[dict] = None
