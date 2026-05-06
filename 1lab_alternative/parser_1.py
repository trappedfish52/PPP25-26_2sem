"""
ETL-процесс: извлечение, трансформация и загрузка данных
=========================================================
Источники:
  1. books.toscrape.com  — книги (название, цена, рейтинг, категория)
  2. quotes.toscrape.com — цитаты (текст, автор, теги)

Целевая БД: SQLite (parser-1.db)
"""

import sqlite3
import json
import re
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request
from urllib.parse import urljoin
from html.parser import HTMLParser

# ─────────────────────────── Настройка логов ────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ETL")

RAW_DIR = Path("raw_data")
RAW_DIR.mkdir(exist_ok=True)

DB_PATH = "etl_database.db"


# ═══════════════════════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ИНСТРУМЕНТЫ
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_html(url: str) -> str:
    """Загружает HTML-страницу и возвращает её как строку."""
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (ETL-Bot/1.0)"})
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ═══════════════════════════════════════════════════════════════════════════════
#  ИСТОЧНИК 1: books.toscrape.com
# ═══════════════════════════════════════════════════════════════════════════════

class BookParser(HTMLParser):
    """Парсит страницу каталога книг."""

    RATING_MAP = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

    def __init__(self):
        super().__init__()
        self.books: list[dict] = []
        self._in_article = False
        self._current: dict = {}
        self._capture_title = False
        self._capture_price = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article" and "product_pod" in attrs.get("class", ""):
            self._in_article = True
            self._current = {}
        if not self._in_article:
            return
        if tag == "p":
            cls = attrs.get("class", "")
            if cls.startswith("star-rating"):
                word = cls.split()[-1]
                self._current["rating"] = self.RATING_MAP.get(word, 0)
            elif cls == "price_color":
                self._capture_price = True
        if tag == "h3":
            self._capture_title = True
        if tag == "a" and self._capture_title:
            self._current["title"] = attrs.get("title", "")
            self._capture_title = False

    def handle_data(self, data):
        if self._capture_price and self._in_article:
            self._current["price_raw"] = data.strip()
            self._capture_price = False

    def handle_endtag(self, tag):
        if tag == "article" and self._in_article:
            self._in_article = False
            if self._current:
                self.books.append(self._current)
                self._current = {}


def extract_books(max_pages: int = 3) -> list[dict]:
    """
    EXTRACT — Источник 1: книги.
    Обходит несколько страниц каталога и возвращает сырые данные.
    """
    base = "https://books.toscrape.com/catalogue/"
    raw_books: list[dict] = []

    for page in range(1, max_pages + 1):
        url = f"{base}page-{page}.html"
        log.info("[Source 1] Загрузка страницы %d → %s", page, url)
        try:
            html = fetch_html(url)
        except Exception as exc:
            log.warning("[Source 1] Ошибка загрузки страницы %d: %s", page, exc)
            break

        parser = BookParser()
        parser.feed(html)
        log.info("[Source 1] Найдено книг на странице %d: %d", page, len(parser.books))
        raw_books.extend(parser.books)

    # Сохраняем сырые данные
    raw_path = RAW_DIR / "raw_books.json"
    raw_path.write_text(json.dumps(raw_books, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("[Source 1] Сырые данные сохранены → %s (%d записей)", raw_path, len(raw_books))
    return raw_books


# ═══════════════════════════════════════════════════════════════════════════════
#  ИСТОЧНИК 2: quotes.toscrape.com
# ═══════════════════════════════════════════════════════════════════════════════

class QuoteParser(HTMLParser):
    """Парсит страницу цитат."""

    def __init__(self):
        super().__init__()
        self.quotes: list[dict] = []
        self._in_quote_div = False
        self._capture_text = False
        self._capture_author = False
        self._capture_tag = False
        self._current: dict = {}
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        cls = attrs_d.get("class", "")
        if tag == "div" and "quote" in cls.split():
            self._in_quote_div = True
            self._depth = 0
            self._current = {"tags": []}
        if not self._in_quote_div:
            return
        if tag == "div":
            self._depth += 1
        if tag == "span" and "text" in cls.split():
            self._capture_text = True
        if tag == "small" and "author" in cls.split():
            self._capture_author = True
        if tag == "a" and "tag" in cls.split():
            self._capture_tag = True

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return
        if self._capture_text:
            self._current["text_raw"] = data
            self._capture_text = False
        elif self._capture_author:
            self._current["author"] = data
            self._capture_author = False
        elif self._capture_tag:
            self._current["tags"].append(data)
            self._capture_tag = False

    def handle_endtag(self, tag):
        if not self._in_quote_div:
            return
        if tag == "div":
            self._depth -= 1
            if self._depth <= 0:
                self._in_quote_div = False
                if self._current.get("text_raw"):
                    self.quotes.append(self._current)
                self._current = {}


def extract_quotes(max_pages: int = 3) -> list[dict]:
    """
    EXTRACT — Источник 2: цитаты.
    """
    base = "https://quotes.toscrape.com"
    raw_quotes: list[dict] = []

    for page in range(1, max_pages + 1):
        url = f"{base}/page/{page}/"
        log.info("[Source 2] Загрузка страницы %d → %s", page, url)
        try:
            html = fetch_html(url)
        except Exception as exc:
            log.warning("[Source 2] Ошибка загрузки страницы %d: %s", page, exc)
            break

        parser = QuoteParser()
        parser.feed(html)
        log.info("[Source 2] Найдено цитат на странице %d: %d", page, len(parser.quotes))
        raw_quotes.extend(parser.quotes)

    raw_path = RAW_DIR / "raw_quotes.json"
    raw_path.write_text(json.dumps(raw_quotes, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("[Source 2] Сырые данные сохранены → %s (%d записей)", raw_path, len(raw_quotes))
    return raw_quotes


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANSFORM
# ═══════════════════════════════════════════════════════════════════════════════

def clean_price(raw: str) -> Optional[float]:
    """'Â£51.77' → 51.77"""
    digits = re.sub(r"[^\d.]", "", raw)
    try:
        return round(float(digits), 2)
    except ValueError:
        return None


def make_uid(*parts: str) -> str:
    """Стабильный идентификатор из набора строк."""
    key = "|".join(parts).encode()
    return hashlib.md5(key).hexdigest()[:12]


def transform_books(raw: list[dict]) -> list[dict]:
    """
    TRANSFORM — книги:
      - очистка цены (убираем символы валюты, конвертируем в float)
      - нормализация рейтинга (1–5)
      - генерация уникального id
      - удаление дубликатов по названию
      - приведение к единой схеме items
    """
    seen: set[str] = set()
    result: list[dict] = []

    for raw_item in raw:
        title = (raw_item.get("title") or "").strip()
        if not title:
            continue

        uid = make_uid("book", title)
        if uid in seen:
            continue
        seen.add(uid)

        price = clean_price(raw_item.get("price_raw") or "")
        rating = raw_item.get("rating")
        if isinstance(rating, int) and 1 <= rating <= 5:
            pass
        else:
            rating = None

        result.append({
            "uid": uid,
            "source": "books.toscrape.com",
            "category": "book",
            "title": title,
            "price": price,
            "rating": rating,
            "description": None,
            "tags": None,
            "scraped_at": datetime.utcnow().isoformat(),
        })

    log.info("[Transform] Книги: %d сырых → %d после трансформации", len(raw), len(result))
    return result


def transform_quotes(raw: list[dict]) -> list[dict]:
    """
    TRANSFORM — цитаты:
      - удаление типографских кавычек из текста
      - нормализация тегов в строку через запятую
      - генерация уникального id
      - удаление дубликатов по тексту
      - приведение к единой схеме items
    """
    seen: set[str] = set()
    result: list[dict] = []

    for raw_item in raw:
        raw_text = (raw_item.get("text_raw") or "").strip()
        # Убираем типографские кавычки « » " " ‟ и обычные
        text = re.sub(r'[«»\u201c\u201d\u201f\u2018\u2019\u00ab\u00bb]', '', raw_text).strip()
        if not text:
            continue

        uid = make_uid("quote", text)
        if uid in seen:
            continue
        seen.add(uid)

        author = (raw_item.get("author") or "").strip() or None
        tags_list = [t.strip() for t in raw_item.get("tags", []) if t.strip()]
        tags_str = ", ".join(tags_list) if tags_list else None

        result.append({
            "uid": uid,
            "source": "quotes.toscrape.com",
            "category": "quote",
            "title": text[:120],           # используем начало цитаты как «заголовок»
            "price": None,
            "rating": None,
            "description": f"Author: {author}" if author else None,
            "tags": tags_str,
            "scraped_at": datetime.utcnow().isoformat(),
        })

    log.info("[Transform] Цитаты: %d сырых → %d после трансформации", len(raw), len(result))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  LOAD
# ═══════════════════════════════════════════════════════════════════════════════

DDL = """
CREATE TABLE IF NOT EXISTS items (
    uid         TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    category    TEXT NOT NULL,
    title       TEXT NOT NULL,
    price       REAL,
    rating      INTEGER,
    description TEXT,
    tags        TEXT,
    scraped_at  TEXT NOT NULL,
    loaded_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_source   ON items(source);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
"""

INSERT_SQL = """
INSERT INTO items (uid, source, category, title, price, rating, description, tags, scraped_at, loaded_at)
VALUES (:uid, :source, :category, :title, :price, :rating, :description, :tags, :scraped_at, :loaded_at)
ON CONFLICT(uid) DO UPDATE SET
    title       = excluded.title,
    price       = excluded.price,
    rating      = excluded.rating,
    description = excluded.description,
    tags        = excluded.tags,
    scraped_at  = excluded.scraped_at,
    loaded_at   = excluded.loaded_at
"""


def load(items: list[dict], db_path: str = DB_PATH) -> None:
    """
    LOAD — загружает унифицированные записи в SQLite.
    Поддерживает UPSERT (INSERT OR UPDATE) для идемпотентного запуска.
    """
    now = datetime.utcnow().isoformat()
    for item in items:
        item["loaded_at"] = now

    con = sqlite3.connect(db_path)
    try:
        con.executescript(DDL)
        cur = con.executemany(INSERT_SQL, items)
        con.commit()
        log.info("[Load] Загружено/обновлено %d записей в '%s'", cur.rowcount, db_path)
    finally:
        con.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  ОТЧЁТ ПО БД
# ═══════════════════════════════════════════════════════════════════════════════

def print_report(db_path: str = DB_PATH) -> None:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        print("\n" + "═" * 55)
        print("  ОТЧЁТ ПО БАЗЕ ДАННЫХ:", db_path)
        print("═" * 55)

        rows = con.execute(
            "SELECT category, source, COUNT(*) AS cnt FROM items GROUP BY category, source"
        ).fetchall()
        print(f"\n  {'Категория':<12} {'Источник':<30} {'Кол-во':>6}")
        print(f"  {'-'*12} {'-'*30} {'-'*6}")
        for r in rows:
            print(f"  {r['category']:<12} {r['source']:<30} {r['cnt']:>6}")

        total = con.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        print(f"\n  Итого записей: {total}")

        print("\n  Примеры книг (топ-3 по рейтингу):")
        for r in con.execute(
            "SELECT title, price, rating FROM items WHERE category='book' AND rating IS NOT NULL "
            "ORDER BY rating DESC LIMIT 3"
        ):
            print(f"    ★{r['rating']}  £{r['price']:>6.2f}  {r['title'][:50]}")

        print("\n  Примеры цитат (первые 3):")
        for r in con.execute(
            "SELECT title, description, tags FROM items WHERE category='quote' LIMIT 3"
        ):
            author = (r["description"] or "").replace("Author: ", "")
            tags = r["tags"] or "—"
            print(f"    [{author}] «{r['title'][:55]}…»")
            print(f"      теги: {tags}")

        print("═" * 55 + "\n")
    finally:
        con.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  ТОЧКА ВХОДА
# ═══════════════════════════════════════════════════════════════════════════════

def run_etl(pages: int = 3):
    log.info("━━━ Запуск ETL-процесса (страниц: %d) ━━━", pages)
    start = datetime.utcnow()

    # ── EXTRACT ──────────────────────────────────────────────
    raw_books = extract_books(max_pages=pages)
    raw_quotes = extract_quotes(max_pages=pages)

    # ── TRANSFORM ────────────────────────────────────────────
    books = transform_books(raw_books)
    quotes = transform_quotes(raw_quotes)
    all_items = books + quotes

    # ── LOAD ─────────────────────────────────────────────────
    load(all_items)

    elapsed = (datetime.utcnow() - start).total_seconds()
    log.info("━━━ ETL завершён за %.1f сек. ━━━", elapsed)

    print_report()


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="ETL: books + quotes → SQLite")
    ap.add_argument("--pages", type=int, default=3, help="Количество страниц с каждого сайта (default: 3)")
    ap.add_argument("--db", type=str, default=DB_PATH, help="Путь к SQLite-файлу")
    args = ap.parse_args()

    DB_PATH = args.db
    run_etl(pages=args.pages)
