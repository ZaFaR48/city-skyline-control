from __future__ import annotations

import pytest

from app.zones.validators import validate_polygon_points


def test_polygon_minimum_points() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        validate_polygon_points([{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.2}])


def test_normalized_coordinate_validation() -> None:
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        validate_polygon_points([
            {"x": 0.1, "y": 0.1},
            {"x": 1.2, "y": 0.2},
            {"x": 0.2, "y": 0.5},
        ])


def test_zero_area_rejection() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        validate_polygon_points([
            {"x": 0.1, "y": 0.1},
            {"x": 0.2, "y": 0.2},
            {"x": 0.3, "y": 0.3},
        ])


def test_duplicate_consecutive_point_rejection() -> None:
    with pytest.raises(ValueError, match="duplicate consecutive"):
        validate_polygon_points([
            {"x": 0.1, "y": 0.1},
            {"x": 0.1, "y": 0.1},
            {"x": 0.3, "y": 0.6},
        ])


def test_self_intersection_detection() -> None:
    with pytest.raises(ValueError, match="self-intersect"):
        validate_polygon_points([
            {"x": 0.1, "y": 0.1},
            {"x": 0.9, "y": 0.9},
            {"x": 0.9, "y": 0.1},
            {"x": 0.1, "y": 0.9},
        ])
