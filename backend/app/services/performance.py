from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
import json
import logging
from time import perf_counter
from typing import Any

from sqlalchemy import event

from ..database import engine


logger = logging.getLogger("city_skyline.performance")


@dataclass
class RequestMetrics:
    query_count: int = 0
    database_duration_ms: float = 0.0
    resolver_duration_ms: float = 0.0
    result_count: int | None = None


_metrics: ContextVar[RequestMetrics | None] = ContextVar("request_metrics", default=None)


def begin_request_metrics() -> Token[RequestMetrics | None]:
    return _metrics.set(RequestMetrics())


def finish_request_metrics(token: Token[RequestMetrics | None]) -> None:
    _metrics.reset(token)


def record_resolver_duration(duration_ms: float) -> None:
    metrics = _metrics.get()
    if metrics is not None:
        metrics.resolver_duration_ms += duration_ms


def record_result_count(count: int) -> None:
    metrics = _metrics.get()
    if metrics is not None:
        metrics.result_count = count


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _query_started(
    _connection: Any,
    _cursor: Any,
    _statement: str,
    _parameters: Any,
    context: Any,
    _executemany: bool,
) -> None:
    if _metrics.get() is not None:
        context._city_skyline_query_started = perf_counter()


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _query_finished(
    _connection: Any,
    _cursor: Any,
    _statement: str,
    _parameters: Any,
    context: Any,
    _executemany: bool,
) -> None:
    metrics = _metrics.get()
    started = getattr(context, "_city_skyline_query_started", None)
    if metrics is not None and started is not None:
        metrics.query_count += 1
        metrics.database_duration_ms += (perf_counter() - started) * 1000


class SlowRequestTimingMiddleware:
    """Log structured, credential-free metrics only for requests over 500 ms."""

    def __init__(self, app: Any, threshold_ms: float = 500.0) -> None:
        self.app = app
        self.threshold_ms = threshold_ms

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        token = begin_request_metrics()
        started = perf_counter()
        status_code = 500

        async def capture_status(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            duration_ms = (perf_counter() - started) * 1000
            metrics = _metrics.get() or RequestMetrics()
            if duration_ms >= self.threshold_ms:
                logger.warning(
                    json.dumps(
                        {
                            "event": "slow_request",
                            "route": scope.get("path", ""),
                            "method": scope.get("method", ""),
                            "status_code": status_code,
                            "total_duration_ms": round(duration_ms, 2),
                            "query_count": metrics.query_count,
                            "database_duration_ms": round(metrics.database_duration_ms, 2),
                            "resolver_duration_ms": round(metrics.resolver_duration_ms, 2),
                            "result_count": metrics.result_count,
                        },
                        separators=(",", ":"),
                    )
                )
            finish_request_metrics(token)
