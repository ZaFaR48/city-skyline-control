from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_repository
from app.database.repositories import EdgeRepository
from app.zones.geometry import bounding_boxes_overlap
from app.zones.models import (
    ParkingSlotCreate,
    ParkingSlotPatch,
    ParkingSlotRead,
    PolygonZoneCreate,
    PolygonZonePatch,
    PolygonZoneRead,
)

router = APIRouter(tags=["zones"])


@router.get("/zones", response_model=list[PolygonZoneRead])
def list_zones(
    preset_id: str | None = None,
    repository: EdgeRepository = Depends(get_repository),
) -> list[PolygonZoneRead]:
    zones = repository.list_zones(preset_id=preset_id)
    return [PolygonZoneRead.model_validate(zone | {"warnings": _zone_warnings(zone, zones)}) for zone in zones]


@router.post("/zones", response_model=PolygonZoneRead, status_code=201)
def create_zone(
    payload: PolygonZoneCreate,
    repository: EdgeRepository = Depends(get_repository),
) -> PolygonZoneRead:
    try:
        zone = repository.create_zone(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    zones = repository.list_zones(preset_id=zone["preset_id"])
    return PolygonZoneRead.model_validate(zone | {"warnings": _zone_warnings(zone, zones)})


@router.patch("/zones/{zone_id}", response_model=PolygonZoneRead)
def update_zone(
    zone_id: str,
    payload: PolygonZonePatch,
    repository: EdgeRepository = Depends(get_repository),
) -> PolygonZoneRead:
    try:
        zone = repository.update_zone(zone_id, payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    zones = repository.list_zones(preset_id=zone["preset_id"])
    return PolygonZoneRead.model_validate(zone | {"warnings": _zone_warnings(zone, zones)})


@router.delete("/zones/{zone_id}", status_code=204)
def delete_zone(zone_id: str, repository: EdgeRepository = Depends(get_repository)) -> None:
    if not repository.delete_zone(zone_id):
        raise HTTPException(status_code=404, detail="Zone not found")


@router.get("/slots", response_model=list[ParkingSlotRead])
def list_slots(
    preset_id: str | None = None,
    zone_id: str | None = None,
    repository: EdgeRepository = Depends(get_repository),
) -> list[ParkingSlotRead]:
    return [ParkingSlotRead.model_validate(slot) for slot in repository.list_slots(preset_id=preset_id, zone_id=zone_id)]


@router.post("/slots", response_model=ParkingSlotRead, status_code=201)
def create_slot(
    payload: ParkingSlotCreate,
    repository: EdgeRepository = Depends(get_repository),
) -> ParkingSlotRead:
    try:
        return ParkingSlotRead.model_validate(repository.create_slot(payload))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/slots/{slot_id}", response_model=ParkingSlotRead)
def update_slot(
    slot_id: str,
    payload: ParkingSlotPatch,
    repository: EdgeRepository = Depends(get_repository),
) -> ParkingSlotRead:
    try:
        slot = repository.update_slot(slot_id, payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found")
    return ParkingSlotRead.model_validate(slot)


@router.delete("/slots/{slot_id}", status_code=204)
def delete_slot(slot_id: str, repository: EdgeRepository = Depends(get_repository)) -> None:
    if not repository.delete_slot(slot_id):
        raise HTTPException(status_code=404, detail="Slot not found")


def _zone_warnings(zone: dict, zones: list[dict]) -> list[str]:
    warnings = []
    for other in zones:
        if other["id"] == zone["id"]:
            continue
        if other["preset_id"] == zone["preset_id"] and bounding_boxes_overlap(
            zone["polygon_points"],
            other["polygon_points"],
        ):
            warnings.append(f"Zone may overlap with {other['code']}.")
    return warnings
