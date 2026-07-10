from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/tariff", tags=["tariff"])


@router.get("")
def get_tariff(request: Request) -> dict:
    config = request.app.state.config
    return {
        "timezone": config.parking_timezone,
        "start_time": config.parking_start_time,
        "end_time": config.parking_end_time,
        "free_minutes": config.parking_free_minutes,
        "rate_tjs_per_hour": config.parking_rate_tjs_per_hour,
        "rounding_mode": config.parking_rounding_mode,
        "rounding_policy_note": "Pilot default is exact_minute; final business/legal policy must confirm rounding.",
        "charges_outside_paid_hours": False,
    }
