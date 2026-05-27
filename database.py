"""DB 연결: DATABASE_URL 이 있으면 Supabase(Postgres), 없으면 로컬 SQLite."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DB_PATH = Path(__file__).resolve().parent / "users.db"

_PG_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_approved   BOOLEAN NOT NULL DEFAULT FALSE,
    is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_SQLITE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    password_hash TEXT  NOT NULL,
    is_approved INTEGER NOT NULL DEFAULT 0,
    is_admin    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
"""


def _validate_postgres_url(url: str) -> None:
    """자주 나는 Supabase 연결 문자열 오류를 미리 안내."""
    lowered = url.lower()
    if "xxxxx" in lowered or "your-password" in lowered or "your_password" in lowered:
        raise RuntimeError(
            "DATABASE_URL에 예시 값(xxxxx 등)이 그대로 있습니다. "
            "Supabase 대시보드에서 Connection string을 다시 복사해 Render에 넣으세요."
        )

    parsed = urlparse(url)
    host = parsed.hostname or ""
    user = parsed.username or ""

    if "pooler.supabase.com" in host and user == "postgres":
        raise RuntimeError(
            "Transaction/Session pooler(포트 6543/5432)는 사용자 이름이 "
            "'postgres'가 아니라 'postgres.프로젝트ID' 형식이어야 합니다. "
            "Supabase → Project Settings → Database → Connection string → URI 에서 "
            "표시되는 전체 문자열을 그대로 복사하세요."
        )


def _postgres_url() -> str | None:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return None
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    _validate_postgres_url(url)
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


def using_postgres() -> bool:
    return _postgres_url() is not None


def _adapt_sql(sql: str) -> str:
    if using_postgres():
        return sql.replace("?", "%s")
    return sql


class DbCursor:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cursor.fetchall()


class DbConnection:
    """SQLite / Postgres 공통 인터페이스 (? 플레이스홀더)."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def execute(self, sql: str, params: tuple | list = ()) -> DbCursor:
        cur = self._raw.cursor()
        cur.execute(_adapt_sql(sql), params)
        return DbCursor(cur)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()


@contextmanager
def get_conn() -> Iterator[DbConnection]:
    pg_url = _postgres_url()
    if pg_url:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        raw = psycopg2.connect(pg_url, cursor_factory=RealDictCursor)
        conn = DbConnection(raw)
        try:
            yield conn
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()
    else:
        raw = sqlite3.connect(DB_PATH)
        raw.row_factory = sqlite3.Row
        conn = DbConnection(raw)
        try:
            yield conn
            raw.commit()
        finally:
            raw.close()


def init_db() -> None:
    sql = _PG_SQL if using_postgres() else _SQLITE_SQL
    with get_conn() as conn:
        conn.execute(sql)
