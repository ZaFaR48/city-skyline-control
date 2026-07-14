from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, select

from app.models import HeadscaleNode, OperationalRegion, PingHistory, Station
from app.services.dashboard import build_dashboard_summary
from app.services.station_health import resolve_station_health_batch


@contextmanager
def captured_queries(db):
    statements: list[str] = []

    def before_cursor_execute(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    connection = db.bind.sync_connection
    event.listen(connection, "before_cursor_execute", before_cursor_execute)
    try:
        yield statements
    finally:
        event.remove(connection, "before_cursor_execute", before_cursor_execute)


async def add_monitored_station(
    db,
    code: str,
    *,
    status: str = "online",
    latency: float = 40,
    recovery_samples: int = 0,
) -> Station:
    city = (
        await db.execute(select(OperationalRegion).where(OperationalRegion.code == "dushanbe"))
    ).scalar_one()
    now = datetime.now(timezone.utc)
    row = Station(
        station_code=code,
        name=f"Performance {code}",
        city_id=city.id,
        address="",
        vpn_ip=f"100.99.0.{int(code[-2:])}",
        status=status,
        status_reason="PING_HIGH_LATENCY: 220 ms" if status == "degraded" else "HEALTHY",
        consecutive_low_latency=recovery_samples,
        recovery_started_at=now - timedelta(seconds=60) if recovery_samples else None,
        approved_at=now,
        is_active=True,
        is_archived=False,
        last_ping_ms=round(latency),
    )
    db.add(row)
    await db.flush()
    db.add(
        HeadscaleNode(
            node_key=f"node-{code}",
            hostname=f"node-{code}",
            vpn_ip=row.vpn_ip,
            station_id=row.id,
            device_type="station",
            approval_status="approved",
            online=True,
        )
    )
    db.add(
        PingHistory(
            station_id=row.id,
            success=True,
            latency_ms=latency,
            checked_at=now - timedelta(seconds=5),
        )
    )
    await db.flush()
    return row


@pytest.mark.asyncio
async def test_batch_resolver_query_count_is_constant_and_latest_ping_is_selected(db):
    stations = [await add_monitored_station(db, f"9300{index}") for index in range(1, 5)]
    newest = datetime.now(timezone.utc)
    db.add(
        PingHistory(
            station_id=stations[0].id,
            success=True,
            latency_ms=77,
            checked_at=newest,
        )
    )
    await db.flush()

    with captured_queries(db) as one_station_queries:
        await resolve_station_health_batch(db, stations[:1])
    with captured_queries(db) as four_station_queries:
        health = await resolve_station_health_batch(db, stations)

    assert len(one_station_queries) == len(four_station_queries) == 4
    assert health[stations[0].id].observed_at == newest
    latest_sql = next(statement for statement in four_station_queries if "latest_ping" in statement)
    assert "LATERAL" in latest_sql and "LIMIT" in latest_sql


@pytest.mark.asyncio
async def test_dashboard_is_bounded_excludes_healthy_and_preserves_hysteresis(db):
    first = await add_monitored_station(db, "94001", latency=40)
    with captured_queries(db) as one_station_queries:
        await build_dashboard_summary(db)
    rows = [
        first,
        await add_monitored_station(db, "94002", latency=45),
        await add_monitored_station(db, "94003", latency=50),
        await add_monitored_station(
            db, "94004", status="degraded", latency=154, recovery_samples=2
        ),
        await add_monitored_station(db, "94005", status="degraded", latency=185),
    ]

    with captured_queries(db) as queries:
        summary = await build_dashboard_summary(db)

    assert len(one_station_queries) == len(queries) == 9
    assert summary.total_stations == 5
    assert summary.total_stations == (
        summary.online_stations
        + summary.degraded_stations
        + summary.offline_stations
        + summary.unknown_stations
    )
    assert (summary.online_stations, summary.degraded_stations) == (3, 2)
    assert len(summary.top_problem_stations) == 2
    assert {item.station_code for item in summary.top_problem_stations} == {"94004", "94005"}
    assert not ({row.station_code for row in rows[:3]} & {item.station_code for item in summary.top_problem_stations})

    recovering = next(item for item in summary.top_problem_stations if item.station_code == "94004")
    assert recovering.status.value == "degraded"
    assert recovering.last_ping_ms == 154
    assert recovering.health.recovery_samples == 2
    assert recovering.health.recovery_samples_required == 3
    assert recovering.health.recovery_stable_seconds_elapsed < 90
    assert all("checked_at >=" not in statement.lower() for statement in queries)
    status_event_queries = [statement.lower() for statement in queries if "station_status_events" in statement.lower()]
    assert len(status_event_queries) == 1
    assert "ended_at is null" in status_event_queries[0]
