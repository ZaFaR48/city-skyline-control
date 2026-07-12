from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.models import AuditLog, OperationalRegion, Station
from app.services.operations_summary import SUMMARY_ACTION, deliver_operations_summary, format_operations_summary


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
    )
    db.add(row)
    await db.flush()
    return row


@pytest.mark.asyncio
async def test_ten_minute_batch_groups_new_and_updated_station_details(db):
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
    assert "Newly created stations" in text and "Updated stations" in text
    assert row.station_code in text and row.name in text
    assert "Customs" in text and "Rudaki 10" in text
    assert "Old address" in text and "100.64.10.1" in text


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
