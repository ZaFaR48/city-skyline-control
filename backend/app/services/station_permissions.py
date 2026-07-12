from fastapi import HTTPException

from ..models import Role, User


OPERATOR_STATION_FIELDS = {
    "city_id",
    "district_id",
    "operational_area",
    "address",
    "name",
    "latitude",
    "longitude",
}


def enforce_station_create_policy(user: User, values: dict[str, object]) -> None:
    if user.role == Role.admin.value:
        return
    if user.role != Role.operator.value:
        raise HTTPException(403, "Station creation requires ADMIN or OPERATOR")
    denied = [field for field in ("vpn_ip", "local_ip", "rustdesk_id") if values.get(field) is not None]
    if denied:
        raise HTTPException(403, f"OPERATOR cannot set fields during registration: {', '.join(denied)}")


def enforce_station_update_policy(user: User, changes: dict[str, object]) -> None:
    if user.role == Role.admin.value:
        return
    if user.role != Role.operator.value:
        raise HTTPException(403, "Station updates require ADMIN or OPERATOR")
    denied = sorted(set(changes) - OPERATOR_STATION_FIELDS)
    if denied:
        raise HTTPException(403, f"OPERATOR cannot update fields: {', '.join(denied)}")
