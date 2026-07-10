from __future__ import annotations

from collections.abc import Sequence


Point = dict[str, float]


def polygon_area(points: Sequence[Point]) -> float:
    area = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        area += point["x"] * next_point["y"] - next_point["x"] * point["y"]
    return abs(area) / 2.0


def has_duplicate_consecutive_points(points: Sequence[Point]) -> bool:
    for index in range(len(points)):
        current = points[index]
        next_point = points[(index + 1) % len(points)]
        if current["x"] == next_point["x"] and current["y"] == next_point["y"]:
            return True
    return False


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b["y"] - a["y"]) * (c["x"] - b["x"]) - (b["x"] - a["x"]) * (c["y"] - b["y"])


def _on_segment(a: Point, b: Point, c: Point) -> bool:
    return (
        min(a["x"], c["x"]) <= b["x"] <= max(a["x"], c["x"])
        and min(a["y"], c["y"]) <= b["y"] <= max(a["y"], c["y"])
    )


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)

    if o1 * o2 < 0 and o3 * o4 < 0:
        return True
    if o1 == 0 and _on_segment(a, c, b):
        return True
    if o2 == 0 and _on_segment(a, d, b):
        return True
    if o3 == 0 and _on_segment(c, a, d):
        return True
    if o4 == 0 and _on_segment(c, b, d):
        return True
    return False


def is_self_intersecting(points: Sequence[Point]) -> bool:
    edge_count = len(points)
    for first_index in range(edge_count):
        a = points[first_index]
        b = points[(first_index + 1) % edge_count]
        for second_index in range(first_index + 1, edge_count):
            if abs(first_index - second_index) <= 1:
                continue
            if first_index == 0 and second_index == edge_count - 1:
                continue
            c = points[second_index]
            d = points[(second_index + 1) % edge_count]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def bounding_boxes_overlap(first: Sequence[Point], second: Sequence[Point]) -> bool:
    first_x = [point["x"] for point in first]
    first_y = [point["y"] for point in first]
    second_x = [point["x"] for point in second]
    second_y = [point["y"] for point in second]
    return not (
        max(first_x) < min(second_x)
        or max(second_x) < min(first_x)
        or max(first_y) < min(second_y)
        or max(second_y) < min(first_y)
    )
