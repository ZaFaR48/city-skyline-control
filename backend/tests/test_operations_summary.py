from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models import AuditLog, OperationalRegion, Station, StationStatusEvent, TelegramIdentity, TelegramSummarySetting, User
from app.services.operations_summary import SUMMARY_ACTION, deliver_operations_summary, format_operations_summary, reduce_status_events


async def station(db, code="93401"):
    city = (await db.execute(select(OperationalRegion).where(OperationalRegion.code == "dushanbe"))).scalar_one()
    district = (await db.execute(select(OperationalRegion).where(OperationalRegion.code == "sino"))).scalar_one()
    row = Station(
        station_code=code,
        name=f"Station {code}",
        city_id=city.id,
        district_id=district.id,
        operational_area="Customs",
        address="Rudaki 10",
        vpn_ip="100.64.10.1",
        local_ip="192.168.10.1",
        latitude=38.55,
        longitude=68.77,
        is_active=True,
        is_archived=False,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return row


@pytest.mark.asyncio
async def test_ten_minute_batch_keeps_station_operations_concise(db):
    row = await station(db)
    events = [
        AuditLog(
            action="station.create",
            entity_type="station",
            entity_id=str(row.id),
            after_data={"station_code": row.station_code, "name": row.name},
            timestamp=datetime.now(timezone.utc),
        ),
        AuditLog(
            action="station.update",
            entity_type="station",
            entity_id=str(row.id),
            before_data={"address": "Old address"},
            after_data={"address": row.address},
            timestamp=datetime.now(timezone.utc),
        ),
    ]
    db.add_all(events)
    await db.flush()
    messages = await format_operations_summary(db, events)
    text = "\n".join(messages)
    assert "Амалиёти стансия" in text
    assert row.station_code in text
    assert "Old address" in text
    assert "Customs" not in text and "100.64.10.1" not in text


@pytest.mark.asyncio
async def test_ten_minute_summary_contains_only_meaningful_status_transitions(db):
    row = await station(db, "93405")
    transition = StationStatusEvent(
        station_id=row.id,
        previous_status="online",
        new_status="offline",
        source="ping",
        reason="PING_TIMEOUT: unreachable",
        started_at=datetime.now(timezone.utc),
    )
    db.add(transition)
    await db.flush()
    text = "\n".join(await format_operations_summary(db, [], [transition]))
    assert "Хомӯш шуд" in text
    assert "93405 — бо стансия алоқа нест" in text


@pytest.mark.asyncio
async def test_batch_delivery_is_persistent_and_idempotent(db):
    row = await station(db, "93402")
    db.add(AuditLog(
        action="station.create",
        entity_type="station",
        entity_id=str(row.id),
        after_data={"station_code": row.station_code},
        timestamp=datetime.now(timezone.utc),
    ))
    await db.flush()
    sent = []

    async def sender(text):
        sent.append(text)
        return True

    assert await deliver_operations_summary(db, sender) == 1
    assert await deliver_operations_summary(db, sender) == 0
    assert len(sent) == 1
    assert await db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == SUMMARY_ACTION)) == 1


@pytest.mark.asyncio
async def test_telegram_operator_creation_summary_has_safe_actor_identity(db):
    row = await station(db, "93404")
    event = AuditLog(
        action="station.create",
        entity_type="station",
        entity_id=str(row.id),
        source="telegram",
        after_data={
            "operator_display_name": "Zafar Operator",
            "operator_username": "zafar_operator",
            "telegram_username": "zafar_tg",
            "telegram_user_id": 123456,
            "password": "must-not-appear",
            "access_token": "must-not-appear",
        },
        timestamp=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()
    text = "\n".join(await format_operations_summary(db, [event]))
    assert "Zafar Operator" in text and "zafar_operator" in text and "123456" in text
    assert "must-not-appear" not in text and "password" not in text and "access_token" not in text


@pytest.mark.asyncio
async def test_failed_delivery_does_not_advance_cursor(db):
    row = await station(db, "93403")
    db.add(AuditLog(
        action="station.update",
        entity_type="station",
        entity_id=str(row.id),
        before_data={"name": "Old"},
        after_data={"name": row.name},
        timestamp=datetime.now(timezone.utc),
    ))
    await db.flush()

    async def fail(_text):
        return False

    assert await deliver_operations_summary(db, fail) == 0
    assert await db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == SUMMARY_ACTION)) == 0


@pytest.mark.asyncio
async def test_short_degraded_spike_is_suppressed_and_station_is_not_duplicated(db):
    row = await station(db, "93406")
    now = datetime.now(timezone.utc)
    degraded = StationStatusEvent(
        station_id=row.id, previous_status="online", new_status="degraded", source="ping",
        reason="PING_HIGH_LATENCY: 220 ms", started_at=now - timedelta(seconds=60),
        ended_at=now - timedelta(seconds=30), duration_seconds=30,
    )
    recovered = StationStatusEvent(
        station_id=row.id, previous_status="degraded", new_status="online", source="ping",
        reason="HEALTHY", started_at=now - timedelta(seconds=30),
    )
    db.add_all([degraded, recovered])
    await db.flush()
    reduction = await reduce_status_events(db, [degraded, recovered], now=now)
    assert reduction.stations == []
    assert reduction.suppressed_transient_count == 1
    assert await format_operations_summary(db, [], [degraded, recovered], reduction=reduction) == []


@pytest.mark.asyncio
async def test_sustained_recovery_appears_once_and_never_as_current_problem(db):
    row = await station(db, "93407")
    now = datetime.now(timezone.utc)
    degraded = StationStatusEvent(
        station_id=row.id, previous_status="online", new_status="degraded", source="ping",
        reason="PING_HIGH_LATENCY: 230 ms", started_at=now - timedelta(minutes=3),
        ended_at=now - timedelta(minutes=1), duration_seconds=120,
    )
    recovered = StationStatusEvent(
        station_id=row.id, previous_status="degraded", new_status="online", source="ping",
        reason="HEALTHY", started_at=now - timedelta(minutes=1),
    )
    db.add_all([degraded, recovered])
    await db.flush()
    reduction = await reduce_status_events(db, [degraded, recovered], now=now)
    assert len(reduction.stations) == 1
    assert reduction.stations[0].category == "recovered"
    text = "\n".join(await format_operations_summary(db, [], [degraded, recovered], language="en", reduction=reduction))
    assert text.count(row.station_code) == 1
    assert "Recovered" in text and "Ongoing problems" not in text


@pytest.mark.asyncio
async def test_latency_flapping_is_one_unstable_line_in_each_language(db):
    row = await station(db, "93408")
    now = datetime.now(timezone.utc)
    statuses = [("online", "degraded"), ("degraded", "online"), ("online", "degraded"), ("degraded", "online")]
    events = []
    for index, (previous, current) in enumerate(statuses):
        event = StationStatusEvent(
            station_id=row.id, previous_status=previous, new_status=current, source="ping",
            reason="PING_HIGH_LATENCY: 205 ms" if current == "degraded" else "HEALTHY",
            started_at=now - timedelta(minutes=4 - index),
        )
        events.append(event)
    db.add_all(events)
    await db.flush()
    reduction = await reduce_status_events(db, events, now=now)
    assert len(reduction.stations) == 1 and reduction.stations[0].reason_code == "UNSTABLE_LATENCY"
    expected = {"tj": "таъхири алоқа ноустувор", "ru": "нестабильная задержка", "en": "unstable network latency"}
    for language, phrase in expected.items():
        text = "\n".join(await format_operations_summary(db, [], events, language=language, reduction=reduction))
        assert text.count(row.station_code) == 1
        assert phrase in text


@pytest.mark.asyncio
async def test_authorized_recipients_receive_individual_languages_and_revoked_are_skipped(db, monkeypatch):
    row = await station(db, "93409")
    now = datetime.now(timezone.utc)
    transition = StationStatusEvent(
        station_id=row.id, previous_status="online", new_status="offline", source="ping",
        reason="PING_TIMEOUT: unreachable", started_at=now,
    )
    users = [
        User(username="summary-tj", email="summary-tj@test.invalid", hashed_password="x", role="admin", is_active=True),
        User(username="summary-ru", email="summary-ru@test.invalid", hashed_password="x", role="operator", is_active=True),
        User(username="summary-viewer", email="summary-viewer@test.invalid", hashed_password="x", role="viewer", is_active=True),
        User(username="summary-inactive", email="summary-inactive@test.invalid", hashed_password="x", role="admin", is_active=False),
    ]
    db.add_all([transition, *users])
    await db.flush()
    db.add_all([
        TelegramIdentity(user_id=users[0].id, telegram_user_id=9340901, preferred_language="tj", automatic_summary_recipient=True),
        TelegramIdentity(user_id=users[1].id, telegram_user_id=9340902, preferred_language="ru", automatic_summary_recipient=True),
        TelegramIdentity(user_id=users[2].id, telegram_user_id=9340903, preferred_language="en", automatic_summary_recipient=True),
        TelegramIdentity(user_id=users[3].id, telegram_user_id=9340904, preferred_language="en", automatic_summary_recipient=True),
    ])
    setting = await db.get(TelegramSummarySetting, 1)
    if setting is None:
        db.add(TelegramSummarySetting(id=1, enabled=True, interval_minutes=10))
    else:
        setting.enabled = True
    await db.flush()
    sent = {}

    async def fake_send(chat_id, text):
        sent[chat_id] = text
        return True

    monkeypatch.setattr("app.services.operations_summary.send_telegram_to", fake_send)
    assert await deliver_operations_summary(db, now=now) >= 1
    assert set(sent) == {9340901, 9340902}
    assert "Тағйирот" in sent[9340901]
    assert "Изменения" in sent[9340902]
