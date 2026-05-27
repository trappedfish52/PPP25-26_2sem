"""
app/db.py — конфигурация SQLAlchemy + ORM-модели

Схема данных:
  sources   (1) → (M) items   (1) → (M) item_events
  items     (M) ↔ (M) tags    (через item_tags)
"""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Float, Integer,
    Text, DateTime, ForeignKey, Table, Boolean,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

DATABASE_URL = "sqlite:///./parser.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ── Таблица связи items ↔ tags (M2M) ─────────────────────────────────────────
item_tags = Table(
    "item_tags",
    Base.metadata,
    Column("item_uid", String, ForeignKey("items.uid", ondelete="CASCADE"), primary_key=True),
    Column("tag_id",   Integer, ForeignKey("tags.id",   ondelete="CASCADE"), primary_key=True),
)


# ── Таблица 1: sources ────────────────────────────────────────────────────────
class Source(Base):
    __tablename__ = "sources"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(120), unique=True, nullable=False)   # e.g. "books.toscrape.com"
    url         = Column(String(255))
    category    = Column(String(60))                                  # "book" / "quote"
    is_active   = Column(Boolean, default=True, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    items = relationship("Item", back_populates="source_rel", cascade="all, delete-orphan")


# ── Таблица 2: items ──────────────────────────────────────────────────────────
class Item(Base):
    __tablename__ = "items"

    uid         = Column(String(12), primary_key=True)
    source      = Column(String(120), ForeignKey("sources.name", ondelete="SET NULL"), nullable=True)
    category    = Column(String(60),  nullable=False)
    title       = Column(Text,        nullable=False)
    price       = Column(Float)
    rating      = Column(Integer)
    description = Column(Text)
    tags        = Column(Text)          # legacy строка из ETL
    scraped_at  = Column(String(32))
    loaded_at   = Column(String(32))

    source_rel  = relationship("Source", back_populates="items")
    events      = relationship("ItemEvent", back_populates="item", cascade="all, delete-orphan")
    tag_rels    = relationship("Tag", secondary=item_tags, back_populates="items")


# ── Таблица 3: item_events ────────────────────────────────────────────────────
class ItemEvent(Base):
    __tablename__ = "item_events"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    item_uid    = Column(String(12), ForeignKey("items.uid", ondelete="CASCADE"), nullable=False)
    event_type  = Column(String(60), nullable=False)   # "created" / "updated" / "price_change" / "deleted"
    payload     = Column(Text)                          # JSON-строка с деталями
    created_at  = Column(DateTime, default=datetime.utcnow)

    item        = relationship("Item", back_populates="events")


# ── Таблица 4: tags (нормализованные теги) ────────────────────────────────────
class Tag(Base):
    __tablename__ = "tags"

    id    = Column(Integer, primary_key=True, autoincrement=True)
    name  = Column(String(80), unique=True, nullable=False)

    items = relationship("Item", secondary=item_tags, back_populates="tag_rels")


# ── Dependency для FastAPI ────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
