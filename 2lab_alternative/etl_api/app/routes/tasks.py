"""
app/routes/tasks.py — запуск долгих задач через Celery + опрос статуса
"""

from fastapi import APIRouter, HTTPException, Query
from celery.result import AsyncResult

from app.schemas import TaskOut

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _celery_app():
    """Ленивый импорт чтобы не падать если Redis недоступен при старте."""
    from app.celery_app import celery_app
    return celery_app


# ── POST /tasks/rebuild_stats ─────────────────────────────────────────────────
@router.post("/rebuild_stats", response_model=TaskOut, status_code=202,
             summary="Запустить пересчёт статистики (async)")
def start_rebuild_stats(db_path: str = Query("parser.db", description="Путь к SQLite")):
    try:
        app = _celery_app()
        task = app.send_task("tasks.rebuild_stats", kwargs={"db_path": db_path})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Celery/Redis недоступен: {exc}. Запустите Redis и Celery-воркер.",
        )
    return TaskOut(task_id=task.id, status="pending")


# ── POST /tasks/reimport_source ───────────────────────────────────────────────
@router.post("/reimport_source", response_model=TaskOut, status_code=202,
             summary="Повторный импорт источника (async)")
def start_reimport(
    source_name: str = Query(..., description="Имя источника"),
    pages: int = Query(2, ge=1, le=10),
):
    try:
        app = _celery_app()
        task = app.send_task(
            "tasks.reimport_source",
            kwargs={"source_name": source_name, "pages": pages},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Celery/Redis недоступен: {exc}. Запустите Redis и Celery-воркер.",
        )
    return TaskOut(task_id=task.id, status="pending")


# ── GET /tasks/{task_id} ──────────────────────────────────────────────────────
@router.get("/{task_id}", response_model=TaskOut, summary="Статус/результат задачи")
def get_task_status(task_id: str):
    try:
        app = _celery_app()
        result: AsyncResult = app.AsyncResult(task_id)
        state = result.state

        payload = None
        if state == "SUCCESS":
            payload = result.result
        elif state in ("PROGRESS", "STARTED"):
            payload = result.info
        elif state == "FAILURE":
            payload = {"error": str(result.info)}

        return TaskOut(task_id=task_id, status=state.lower(), result=payload)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Celery/Redis недоступен: {exc}",
        )
