"""
app/routes/ws.py — WebSocket-эндпоинт для отслеживания прогресса задач (Вариант A)

Клиент:
  1. ws://host/ws/{client_id}
  2. POST /tasks/rebuild_stats → получает task_id
  3. Отправляет в WS: {"action": "subscribe", "task_id": "..."}
  4. Сервер каждые 1.5с шлёт {"task_id": "...", "status": "...", "progress": ...}
"""

import asyncio
import json
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

# client_id → WebSocket
_connections: Dict[str, WebSocket] = {}


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    _connections[client_id] = websocket

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Невалидный JSON"})
                continue

            action = msg.get("action")

            if action == "subscribe":
                task_id = msg.get("task_id")
                if not task_id:
                    await websocket.send_json({"error": "task_id обязателен"})
                    continue

                # Запускаем фоновый опрос статуса задачи
                asyncio.create_task(_poll_task(websocket, task_id))

            elif action == "ping":
                await websocket.send_json({"pong": True})

            else:
                await websocket.send_json({"error": f"Неизвестный action: {action}"})

    except WebSocketDisconnect:
        pass
    finally:
        _connections.pop(client_id, None)


async def _poll_task(ws: WebSocket, task_id: str, interval: float = 1.5, max_polls: int = 60):
    """Опрашивает Celery-результат и шлёт обновления по WebSocket."""
    try:
        from app.celery_app import celery_app
    except Exception:
        await ws.send_json({"task_id": task_id, "status": "error", "detail": "Celery недоступен"})
        return

    for _ in range(max_polls):
        try:
            result = celery_app.AsyncResult(task_id)
            state = result.state
            info = result.info if result.info else {}

            payload = {"task_id": task_id, "status": state.lower()}
            if isinstance(info, dict):
                payload.update(info)
            elif state == "FAILURE":
                payload["error"] = str(info)

            await ws.send_json(payload)

            if state in ("SUCCESS", "FAILURE", "REVOKED"):
                break
        except Exception as exc:
            await ws.send_json({"task_id": task_id, "status": "error", "detail": str(exc)})
            break

        await asyncio.sleep(interval)
