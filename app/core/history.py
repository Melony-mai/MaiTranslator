import logging
import sqlite3
import threading
from datetime import datetime

from .paths import data_dir

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    src_lang TEXT NOT NULL,
    tgt_lang TEXT NOT NULL,
    source TEXT NOT NULL,
    result TEXT NOT NULL,
    duration_ms REAL DEFAULT 0,
    chars INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_translations_time ON translations(created_at DESC);
"""


class History:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.db_path = data_dir() / "history.db"
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def add(self, src_lang: str, tgt_lang: str, source: str, result: str, duration_ms: float = 0.0) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO translations(created_at,src_lang,tgt_lang,source,result,duration_ms,chars)"
                " VALUES(?,?,?,?,?,?,?)",
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    src_lang,
                    tgt_lang,
                    source,
                    result,
                    round(duration_ms, 1),
                    len(source),
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def query(self, search: str = "", limit: int = 200, offset: int = 0) -> list[dict]:
        with self._lock:
            if search:
                like = f"%{search}%"
                rows = self._conn.execute(
                    "SELECT id,created_at,src_lang,tgt_lang,source,result,duration_ms FROM translations"
                    " WHERE source LIKE ? OR result LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (like, like, limit, offset),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT id,created_at,src_lang,tgt_lang,source,result,duration_ms"
                    " FROM translations ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [
            dict(zip(["id", "created_at", "src_lang", "tgt_lang", "source", "result", "duration_ms"], r))
            for r in rows
        ]

    def get(self, record_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id,created_at,src_lang,tgt_lang,source,result,duration_ms,chars"
                " FROM translations WHERE id=?",
                (int(record_id),),
            ).fetchone()
        if row is None:
            return None
        return dict(
            zip(
                ["id", "created_at", "src_lang", "tgt_lang", "source", "result", "duration_ms", "chars"],
                row,
            )
        )

    def delete(self, ids: list[int]) -> None:
        with self._lock:
            self._conn.executemany("DELETE FROM translations WHERE id=?", [(i,) for i in ids])
            self._conn.commit()

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM translations")
            self._conn.commit()
            try:
                self._conn.execute("VACUUM")
            except sqlite3.OperationalError:
                pass

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()
