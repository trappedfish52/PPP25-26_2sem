# ETL Web API — FastAPI + SQLite + Celery + WebSocket

REST API поверх ETL-базы данных (`parser.db`), полученной скриптом `main.py`.

---

## Структура проекта

```
etl_api/
├── app/
│   ├── main.py          # FastAPI-приложение, lifespan, подключение роутеров
│   ├── db.py            # SQLAlchemy-модели + engine + get_db
│   ├── schemas.py       # Pydantic-схемы
│   ├── celery_app.py    # Celery-приложение + задачи
│   ├── routes/
│   │   ├── items.py     # CRUD для items + история событий
│   │   ├── sources.py   # CRUD для sources
│   │   ├── stats.py     # Агрегированная статистика
│   │   ├── tasks.py     # Запуск долгих задач + опрос статуса
│   │   └── ws.py        # WebSocket-эндпоинт
│   └── services/
│       └── seed.py      # Инициализация таблиц + сид источников
├── tests/
│   └── test_api.py      # Pytest-тесты без Uvicorn
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## Модель данных

```
sources (1) ──< items (1) ──< item_events
                items (M) >──< tags  (через item_tags)
```

| Таблица       | Назначение                                       |
|---------------|--------------------------------------------------|
| `sources`     | Источники ETL (books.toscrape.com, quotes…)      |
| `items`       | Объединённые сущности из ETL (книги + цитаты)    |
| `item_events` | Лог изменений каждого item                       |
| `tags`        | Нормализованные теги (M2M с items)               |

---

## API-эндпоинты (12 ручек + WebSocket)

### Items
| Метод  | URL                     | Описание                         |
|--------|-------------------------|----------------------------------|
| GET    | `/items/`               | Список с фильтрацией/поиском     |
| GET    | `/items/{uid}`          | Получить item по UID             |
| POST   | `/items/`               | Создать item                     |
| PUT    | `/items/{uid}`          | Полная замена                    |
| PATCH  | `/items/{uid}`          | Частичное обновление             |
| DELETE | `/items/{uid}`          | Удалить item                     |
| GET    | `/items/{uid}/events`   | История событий item             |

### Sources
| Метод  | URL                     | Описание                         |
|--------|-------------------------|----------------------------------|
| GET    | `/sources/`             | Список источников                |
| GET    | `/sources/{id}`         | Источник по ID                   |
| POST   | `/sources/`             | Создать источник                 |
| PUT    | `/sources/{id}`         | Полная замена                    |
| PATCH  | `/sources/{id}`         | Частичное обновление             |
| DELETE | `/sources/{id}`         | Удалить источник                 |

### Stats
| Метод  | URL       | Описание                             |
|--------|-----------|--------------------------------------|
| GET    | `/stats/` | Агрегированная статистика по БД      |

### Tasks (Celery)
| Метод  | URL                        | Описание                              |
|--------|----------------------------|---------------------------------------|
| POST   | `/tasks/rebuild_stats`     | Запустить пересчёт (async) → task_id  |
| POST   | `/tasks/reimport_source`   | Повторный импорт источника            |
| GET    | `/tasks/{task_id}`         | Статус / результат задачи             |

### WebSocket
| URL              | Описание                              |
|------------------|---------------------------------------|
| `ws://…/ws/{id}` | Подписка на прогресс задачи в реальном времени |

---

## Быстрый старт

### 1. Сначала запустите ETL (из оригинального задания)
```bash
pip install certifi
python main.py --pages 3   # создаёт parser.db
```

### 2. Установите зависимости
```bash
cd etl_api
pip install -r requirements.txt
```

### 3. Запуск только API (без Celery/Redis)
```bash
uvicorn app.main:app --reload
# → http://localhost:8000/docs
```

### 4. Полный стек (с Celery + Redis) через Docker Compose
```bash
# Скопируйте parser.db в папку etl_api/
cp ../parser.db .

docker compose up --build
# API    → http://localhost:8000
# Docs   → http://localhost:8000/docs
```

### 5. Запуск тестов
```bash
pytest tests/ -v
```

---

## WebSocket — пример использования (JavaScript)

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/my-client-1");

ws.onopen = () => {
    // 1. Запустить задачу
    fetch("/tasks/rebuild_stats", { method: "POST" })
        .then(r => r.json())
        .then(data => {
            // 2. Подписаться на прогресс
            ws.send(JSON.stringify({ action: "subscribe", task_id: data.task_id }));
        });
};

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    console.log(`[${msg.status}] progress: ${msg.progress ?? "?"}%`);
    // {"task_id": "...", "status": "progress", "progress": 60, "msg": "Подсчёт записей"}
};
```

---

## Пример cURL-запросов

```bash
# Получить список items (книги, рейтинг ≥ 4)
curl "http://localhost:8000/items/?category=book&min_rating=4"

# Создать item
curl -X POST http://localhost:8000/items/ \
  -H "Content-Type: application/json" \
  -d '{"uid":"test00000001","source":"books.toscrape.com","category":"book","title":"Test Book","price":12.99,"rating":5}'

# Частичное обновление цены
curl -X PATCH http://localhost:8000/items/test00000001 \
  -H "Content-Type: application/json" \
  -d '{"price": 9.99}'

# Статистика
curl http://localhost:8000/stats/

# Запустить пересчёт статистики (async)
curl -X POST "http://localhost:8000/tasks/rebuild_stats"

# Проверить статус задачи
curl http://localhost:8000/tasks/<task_id>
```
