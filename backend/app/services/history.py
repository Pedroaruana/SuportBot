import sqlite3
from pathlib import Path

from app.core.config import settings


def _connect() -> sqlite3.Connection:
    path = Path(settings.sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)")
    return conn


def add_message(session_id: str, role: str, content: str) -> None:
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
    finally:
        conn.close()


def get_history(session_id: str, turns: int | None = None) -> list[tuple[str, str]]:
    """Ultimos `turns` turnos (pergunta + resposta), em ordem cronologica."""
    limit = (turns or settings.history_turns) * 2
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    finally:
        conn.close()
    return list(reversed(rows))


def clear_history(session_id: str) -> int:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        return cur.rowcount
    finally:
        conn.close()
