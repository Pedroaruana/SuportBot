import json
import logging
import time
from collections import deque
from threading import Lock


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("supportbot")
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    root.propagate = False


def log(event: str, **fields: object) -> None:
    logging.getLogger("supportbot").info(event, extra={"fields": fields})


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(pct * (len(ordered) - 1))))
    return round(ordered[idx], 1)


class Metrics:
    """Contadores em memoria. Para varias instancias, trocar por Prometheus."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.started_at = time.time()
        self.reset()

    def reset(self) -> None:
        self.requests = 0
        self.errors = 0
        self.chat_requests = 0
        self.fallbacks = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.latency_ms: deque[float] = deque(maxlen=1000)
        self.chat_latency_ms: deque[float] = deque(maxlen=1000)

    def record_request(self, status: int, ms: float) -> None:
        with self._lock:
            self.requests += 1
            if status >= 500:
                self.errors += 1
            self.latency_ms.append(ms)

    def record_chat(self, ms: float, tokens_in: int, tokens_out: int, fallback: bool) -> None:
        with self._lock:
            self.chat_requests += 1
            self.chat_latency_ms.append(ms)
            self.tokens_in += tokens_in
            self.tokens_out += tokens_out
            if fallback:
                self.fallbacks += 1

    def snapshot(self) -> dict:
        with self._lock:
            chat = list(self.chat_latency_ms)
            allr = list(self.latency_ms)
            return {
                "uptime_s": int(time.time() - self.started_at),
                "requests": self.requests,
                "errors_5xx": self.errors,
                "latency_ms": {"p50": _percentile(allr, 0.5), "p95": _percentile(allr, 0.95)},
                "chat": {
                    "requests": self.chat_requests,
                    "fallbacks": self.fallbacks,
                    "latency_ms": {"p50": _percentile(chat, 0.5), "p95": _percentile(chat, 0.95)},
                    "tokens_in": self.tokens_in,
                    "tokens_out": self.tokens_out,
                },
            }


metrics = Metrics()
