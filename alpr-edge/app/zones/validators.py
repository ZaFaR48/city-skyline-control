from __future__ import annotations

from collections.abc import Sequence

from app.zones.geometry import (
    Point,
    has_duplicate_consecutive_points,
    is_self_intersecting,
    polygon_area,
)


def validate_polygon_points(points: Sequence[Point]) -> list[dict[str, float]]:
    if len(points) < 3:
        raise ValueError("polygon requires at least 3 points")

    normalized: list[dict[str, float]] = []
    for point in points:
        x = float(point["x"])
        y = float(point["y"])
        if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
            raise ValueError("polygon coordinates must be between 0.0 and 1.0")
        normalized.append({"x": x, "y": y})

    if has_duplicate_consecutive_points(normalized):
        raise ValueError("polygon contains duplicate consecutive points")
    if is_self_intersecting(normalized):
        raise ValueError("polygon must not self-intersect")
    if polygon_area(normalized) <= 0.000001:
        raise ValueError("polygon area must be greater than zero")
    return normalized
