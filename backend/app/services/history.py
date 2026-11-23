from app.core.config import settings
from app.services.db import connect


def add_message(session_id: str, role: str, content: str) -> None:
    conn = connect()
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
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    finally:
        conn.close()
    return [(r["role"], r["content"]) for r in reversed(rows)]


def clear_history(session_id: str) -> int:
    conn = connect()
    try:
        with conn:
            cur = conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        return cur.rowcount
    finally:
        conn.close()
