#!/usr/bin/env python3
"""Audit questionable production records without deleting anything.

Use --dry-run for the mandatory review report. --apply only performs the
explicitly listed reversible actions (archive obvious demo-named stations,
clear telemetry with no sample provenance, and resolve duplicate open offline
alerts while preserving every alert row).
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Alert,
    AlertType,
    ApprovalStatus,
    Camera,
    HeadscaleNode,
    OperationalRegion,
    Station,
    TelemetrySample,
)


PLACEHOLDER_WORDS = ("demo", "sample", "test station", "placeholder", "example")


async def audit(apply: bool) -> int:
    findings: list[tuple[str, str, str]] = []
    async with SessionLocal() as db:
        stations = (await db.execute(select(Station).order_by(Station.station_code))).scalars().all()
        regions = {row.id: row for row in (await db.execute(select(OperationalRegion))).scalars().all()}
        cameras = (await db.execute(select(Camera).order_by(Camera.id))).scalars().all()
        nodes = (await db.execute(select(HeadscaleNode).order_by(HeadscaleNode.id))).scalars().all()
        alerts = (
            await db.execute(
                select(Alert)
                .where(Alert.resolved_at.is_(None), Alert.type == AlertType.offline_station.value)
                .order_by(Alert.station_id, Alert.created_at)
            )
        ).scalars().all()

        code_counts = Counter(station.station_code for station in stations)
        vpn_counts = Counter(station.vpn_ip for station in stations if station.vpn_ip)
        sample_station_ids = set(
            (await db.execute(select(TelemetrySample.station_id).distinct())).scalars().all()
        )

        for station in stations:
            city = regions.get(station.city_id)
            if not city or city.code != "dushanbe":
                findings.append(("outside_dushanbe", station.station_code, "Review and archive unless explicitly approved for production."))
            if any(word in station.name.casefold() for word in PLACEHOLDER_WORDS):
                findings.append(("placeholder_station", station.station_code, "Verify identity; archive this obvious demo-named record if it is not production."))
                if apply:
                    station.is_archived = True
                    station.is_active = False
            if code_counts[station.station_code] > 1:
                findings.append(("duplicate_station_code", station.station_code, "Assign a unique human-facing station code after administrator review."))
            if station.vpn_ip and vpn_counts[station.vpn_ip] > 1:
                findings.append(("duplicate_vpn_ip", station.station_code, f"VPN IP {station.vpn_ip} is shared; verify Headscale identity and correct the station assignment."))
            if station.district_id is None:
                findings.append(("missing_district", station.station_code, "Assign one verified Dushanbe district; do not infer it from the station name."))
            if station.latitude is None or station.longitude is None:
                findings.append(("missing_coordinates", station.station_code, "Capture verified coordinates before placing this station on the map."))
            if (station.cpu is not None or station.ram is not None or station.disk is not None) and station.id not in sample_station_ids:
                findings.append(("unproven_telemetry", station.station_code, "Clear CPU/RAM/disk because no agent telemetry sample proves the values."))
                if apply:
                    station.cpu = station.ram = station.disk = None
                    station.telemetry_at = None

        for node in nodes:
            if node.station_id is None:
                recommendation = "Classify and approve explicitly; link only if this is a production station device."
                findings.append(("unlinked_headscale_node", f"node:{node.id}", recommendation))

        for camera in cameras:
            if any(word in camera.name.casefold() for word in PLACEHOLDER_WORDS):
                findings.append(("placeholder_camera", f"camera:{camera.id}", "Verify camera identity and configuration; do not count it as monitored until confirmed."))

        alerts_by_station: dict[int | None, list[Alert]] = defaultdict(list)
        for alert in alerts:
            alerts_by_station[alert.station_id].append(alert)
            if any(word in alert.message.casefold() for word in PLACEHOLDER_WORDS):
                findings.append(("demo_alert", f"alert:{alert.id}", "Review and resolve if this was a test; preserve the audit record."))
        now = datetime.now(timezone.utc)
        for station_id, duplicate_alerts in alerts_by_station.items():
            if len(duplicate_alerts) > 1:
                station = next((item for item in stations if item.id == station_id), None)
                identity = station.station_code if station else f"station:{station_id}"
                findings.append(("duplicate_open_offline_alerts", identity, f"Keep the oldest open alert and resolve {len(duplicate_alerts) - 1} duplicates; preserve all rows."))
                if apply:
                    for alert in duplicate_alerts[1:]:
                        alert.resolved_at = now

        print("mode=" + ("apply" if apply else "dry-run"))
        print(f"stations_scanned={len(stations)} cameras_scanned={len(cameras)} headscale_nodes_scanned={len(nodes)}")
        print(f"findings={len(findings)}")
        for category, identity, recommendation in findings:
            print(f"[{category}] {identity}: {recommendation}")
        if apply:
            await db.commit()
            print("Reversible archival/normalization actions committed. No records were deleted.")
        else:
            await db.rollback()
            print("No changes made. Run --apply only after administrator approval and a fresh backup.")
    return 1 if findings else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(audit(args.apply)))


if __name__ == "__main__":
    main()
