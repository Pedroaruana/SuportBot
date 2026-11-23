import re

from app.services.db import connect


def _normalize(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


def record_interaction(session_id: str, question: str, answer: str, fallback: bool, best_score: float | None) -> int:
    """Grava a interacao (pergunta ja redigida) e devolve o id usado no feedback."""
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO interactions (session_id, question, question_norm, answer, fallback, best_score)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, question, _normalize(question), answer, int(fallback), best_score),
            )
        return int(cur.lastrowid)
    finally:
        conn.close()


def set_feedback(message_id: int, rating: int, comment: str | None) -> bool:
    """Grava ou atualiza o feedback. Retorna False se a interacao nao existe."""
    conn = connect()
    try:
        with conn:
            exists = conn.execute("SELECT 1 FROM interactions WHERE id = ?", (message_id,)).fetchone()
            if not exists:
                return False
            conn.execute(
                """INSERT INTO feedback (message_id, rating, comment) VALUES (?, ?, ?)
                   ON CONFLICT(message_id) DO UPDATE SET rating = excluded.rating,
                       comment = excluded.comment, created_at = CURRENT_TIMESTAMP""",
                (message_id, rating, comment),
            )
        return True
    finally:
        conn.close()


def summary() -> dict:
    conn = connect()
    try:
        total, fallbacks = conn.execute("SELECT COUNT(*), COALESCE(SUM(fallback), 0) FROM interactions").fetchone()
        up, down = conn.execute(
            "SELECT COALESCE(SUM(rating = 1), 0), COALESCE(SUM(rating = -1), 0) FROM feedback"
        ).fetchone()
    finally:
        conn.close()
    rated = up + down
    return {
        "interactions": total,
        "fallbacks": fallbacks,
        "fallback_rate": round(fallbacks / total, 3) if total else 0.0,
        "feedback_up": up,
        "feedback_down": down,
        "satisfaction": round(up / rated, 3) if rated else None,
    }


def unanswered(limit: int = 50) -> list[dict]:
    """Perguntas que caíram em fallback, agrupadas, das mais frequentes para as menos."""
    conn = connect()
    try:
        rows = conn.execute(
            """SELECT MIN(question) AS question, COUNT(*) AS count, MAX(created_at) AS last_seen
               FROM interactions WHERE fallback = 1
               GROUP BY question_norm ORDER BY count DESC, last_seen DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def downvoted(limit: int = 50) -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute(
            """SELECT i.id AS message_id, i.question, i.answer, i.fallback, f.comment, f.created_at
               FROM feedback f JOIN interactions i ON i.id = f.message_id
               WHERE f.rating = -1 ORDER BY f.created_at DESC, f.message_id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
