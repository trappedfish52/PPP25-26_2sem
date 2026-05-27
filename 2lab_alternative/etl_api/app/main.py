"""
app/main.py — инициализация FastAPI-приложения
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.db import SessionLocal
from app.services.seed import init_db, seed_sources
from app.routes import items, sources, stats, tasks, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    #создаём таблицы и сеем источники
    init_db()
    db = SessionLocal()
    try:
        seed_sources(db)
    finally:
        db.close()
    yield
    #завершение — можно добавить cleanup


app = FastAPI(
    title="ETL Web API",
    description=(
        "REST API поверх ETL-базы данных (books + quotes).\n\n"
        "Включает: CRUD для items/sources, статистику, "
        "асинхронные задачи (Celery) и WebSocket-прогресс."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

#роутеры
app.include_router(items.router)
app.include_router(sources.router)
app.include_router(stats.router)
app.include_router(tasks.router)
app.include_router(ws.router)


#корневой маршрут
@app.get("/", tags=["root"], summary="Информация об API")
def root():
    return {
        "service": "ETL Web API",
        "docs":    "/docs",
        "redoc":   "/redoc",
        "endpoints": {
            "items":   "/items",
            "sources": "/sources",
            "stats":   "/stats",
            "tasks":   "/tasks",
            "ws":      "/ws/{client_id}",
        },
    }
