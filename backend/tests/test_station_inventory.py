from __future__ import annotations

from datetime import datetime, timezone
from starlette.requests import Request
import pytest
from sqlalchemy import func, select

from app.models import AuditLog, OperationalRegion, Station, User
from app.routers.onboarding import (
    archive_inventory_station,
    preview_station_archive,
    preview_station_restore,
    restore_inventory_station,
    suspected_duplicate_report,
    station_inventory,
)
from app.routers.stations import archive_station as legacy_archive_station
from app.schemas import StationLifecycleApplyIn


def request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("127.0.0.1", 1)})


async def inventory(db, code: str, *, name="Inventory station", address="Rudaki 10", area="Center"):
    city = (await db.execute(select(OperationalRegion).where(OperationalRegion.code == "dushanbe"))).scalar_one()
    district = (await db.execute(select(OperationalRegion).where(OperationalRegion.code == "sino"))).scalar_one()
    admin = User(username=f"inventory-{code}", email=f"inventory-{code}@test.invalid", hashed_password="unchanged", role="admin", is_active=True)
    station = Station(
        station_code=code,
        name=name,
        city_id=city.id,
        district_id=district.id,
        operational_area=area,
        address=address,
        latitude=38.55,
        longitude=68.77,
        is_active=True,
        is_archived=False,
    )
    db.add_all([admin, station])
    await db.flush()
    return station, admin


@pytest.mark.asyncio
async def test_archive_is_soft_and_restore_is_explicit_and_audited(db):
    station, admin = await inventory(db, "93301")
    archive_preview = await preview_station_archive(station.id, db, admin)
    await archive_inventory_station(
        station.id,
        StationLifecycleApplyIn(
            preview_token=archive_preview.preview_token or "",
            confirmation=archive_preview.confirmation_phrase,
        ),
        request(),
        db,
        admin,
    )
    persisted = await db.get(Station, station.id)
    assert persisted is not None
    assert persisted.is_archived and not persisted.is_active
    assert persisted.approved_at is None
    assert await db.scalar(select(func.count()).select_from(Station).where(Station.id == station.id)) == 1

    restore_preview = await preview_station_restore(station.id, db, admin)
    await restore_inventory_station(
        station.id,
        StationLifecycleApplyIn(
            preview_token=restore_preview.preview_token or "",
            confirmation=restore_preview.confirmation_phrase,
        ),
        request(),
        db,
        admin,
    )
    await db.refresh(persisted)
    assert persisted.is_active and not persisted.is_archived
    actions = set((await db.execute(select(AuditLog.action))).scalars().all())
    assert {"station.archive", "station.restore"} <= actions


@pytest.mark.asyncio
async def test_legacy_archive_route_cannot_bypass_typed_confirmation(db):
    station, admin = await inventory(db, "93304")
    with pytest.raises(Exception) as exc:
        await legacy_archive_station(station.id, request(), db, admin)
    assert getattr(exc.value, "status_code", None) == 409
    assert not station.is_archived and station.is_active


@pytest.mark.asyncio
async def test_suspected_duplicate_report_is_read_only_and_explains_indicators(db):
    left, admin = await inventory(db, "93302", name="Sino Customs", address="Rudaki 22", area="Customs")
    right, _ = await inventory(db, "93303", name="Sino Customs", address="Rudaki 22", area="Customs")
    before_audits = int(await db.scalar(select(func.count()).select_from(AuditLog)) or 0)
    report = await suspected_duplicate_report(db, admin)
    pair = next(item for item in report if {item.left.station_id, item.right.station_id} == {left.id, right.id})
    assert {"same normalized name", "same address", "same operational area"} <= set(pair.reasons)
    assert "Review both records" in pair.recommendation
    assert int(await db.scalar(select(func.count()).select_from(AuditLog)) or 0) == before_audits
    assert not left.is_archived and not right.is_archived


@pytest.mark.asyncio
async def test_inventory_search_combines_with_pending_filter_and_operational_fields(db):
    pending, admin = await inventory(db, "93305", name="Search target", address="Rudaki 55", area="Unique Landmark")
    approved, _ = await inventory(db, "93306", name="Search target approved", address="Rudaki 56", area="Unique Landmark")
    approved.approved_at = datetime.now(timezone.utc)
    await db.flush()
    rows = await station_inventory("pending", "Unique Landmark", db, admin)
    assert pending.id in {row.id for row in rows}
    assert approved.id not in {row.id for row in rows}
