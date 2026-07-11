from __future__ import annotations

from sqlalchemy.sql.elements import ColumnElement

from ..models import Station


def production_station_filter() -> ColumnElement[bool]:
    """The single definition of a station visible in production views."""
    return (
        Station.approved_at.is_not(None)
        & Station.is_active.is_(True)
        & Station.is_archived.is_(False)
    )
