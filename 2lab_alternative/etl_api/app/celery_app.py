"""
app/celery_app.py — конфигурация Celery + задачи
"""

import json
import time
import logging
from datetime import datetime
from celery import Celery

log = logging.getLogger("celery_tasks")

# Если Redis недоступен — используем встроенный in-memory брокер для тестов
BROKER_URL  = "redis://localhost:6379/0"
BACKEND_URL = "redis://localhost:6379/0"

celery_app = Celery(
    "etl_api",
    broker=BROKER_URL,
    backend=BACKEND_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


@celery_app.task(bind=True, name="tasks.rebuild_stats")
def rebuild_stats(self, db_path: str = "parser.db"):
    """
    Долгая задача: пересчитывает статистику по БД.
    Имитирует тяжёлую работу через sleep.
    """
    import sqlite3

    self.update_state(state="STARTED", meta={"progress": 0, "msg": "Начало пересчёта"})
    time.sleep(1)

    try:
        con = sqlite3.connect(db_path)
        self.update_state(state="PROGRESS", meta={"progress": 30, "msg": "Подключение к БД"})
        time.sleep(1)

        total = con.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        self.update_state(state="PROGRESS", meta={"progress": 60, "msg": "Подсчёт записей"})
        time.sleep(1)

        by_cat = dict(
            con.execute("SELECT category, COUNT(*) FROM items GROUP BY category").fetchall()
        )
        avg_price = con.execute(
            "SELECT ROUND(AVG(price),2) FROM items WHERE price IS NOT NULL"
        ).fetchone()[0]
        con.close()

        self.update_state(state="PROGRESS", meta={"progress": 90, "msg": "Финализация"})
        time.sleep(0.5)

        result = {
            "total": total,
            "by_category": by_cat,
            "avg_price": avg_price,
            "computed_at": datetime.utcnow().isoformat(),
        }
        return result

    except Exception as exc:
        self.update_state(state="FAILURE", meta={"error": str(exc)})
        raise


@celery_app.task(bind=True, name="tasks.reimport_source")
def reimport_source(self, source_name: str, pages: int = 2):
    """
    Долгая задача: повторный импорт данных из источника.
    """
    self.update_state(state="STARTED", meta={"progress": 0, "source": source_name})
    time.sleep(1)

    # Имитация работы
    for i in range(1, pages + 1):
        self.update_state(
            state="PROGRESS",
            meta={"progress": int(i / pages * 80), "page": i, "source": source_name},
        )
        time.sleep(1)

    self.update_state(state="PROGRESS", meta={"progress": 100, "source": source_name})
    return {"source": source_name, "pages_processed": pages, "done_at": datetime.utcnow().isoformat()}
