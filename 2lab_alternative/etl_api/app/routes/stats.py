"""
app/routes/stats.py — агрегированная статистика
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db, Item
from app.schemas import StatsOut

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/", response_model=StatsOut, summary="Агрегированная статистика по БД")
def get_stats(db: Session = Depends(get_db)):
    from app.db import Source

    total_items   = db.query(func.count(Item.uid)).scalar()
    total_sources = db.query(func.count(Source.id)).scalar()

    rows = db.query(Item.category, func.count(Item.uid)).group_by(Item.category).all()
    by_category = {cat: cnt for cat, cnt in rows}

    avg_price  = db.query(func.round(func.avg(Item.price), 2)).filter(Item.price.isnot(None)).scalar()
    avg_rating = db.query(func.round(func.avg(Item.rating), 2)).filter(Item.rating.isnot(None)).scalar()

    return StatsOut(
        total_items=total_items or 0,
        total_sources=total_sources or 0,
        by_category=by_category,
        avg_price=avg_price,
        avg_rating=avg_rating,
    )
