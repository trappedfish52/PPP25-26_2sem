"""
app/services/seed.py — синхронизация sources из ETL-данных при старте
"""

import logging
from sqlalchemy.orm import Session
from app.db import Source, Item, engine, Base

log = logging.getLogger("seed")

ETL_SOURCES = [
    {"name": "books.toscrape.com", "url": "https://books.toscrape.com", "category": "book"},
    {"name": "quotes.toscrape.com", "url": "https://quotes.toscrape.com", "category": "quote"},
]


def init_db():
    """Создаёт таблицы если их нет."""
    Base.metadata.create_all(bind=engine)
    log.info("Таблицы БД инициализированы")


def seed_sources(db: Session):
    """Добавляет записи в sources на основе ETL-источников (если нет)."""
    for s in ETL_SOURCES:
        existing = db.query(Source).filter(Source.name == s["name"]).first()
        if not existing:
            db.add(Source(**s))
            log.info("Добавлен источник: %s", s["name"])
    db.commit()
