"""Frozen public interface of floorplan/config.py.

P1, P2 (engine.py) and P4 import these names. Removing or renaming any of them
breaks a teammate's module, so this test fails first. Adding new names is fine.
"""
import inspect

from floorplan import config

REQUIRED_CONSTANTS = {
    "GRID_UNIT_FT": 1,
    "CIRCULATION_FACTOR": 0.15,
    "SOLVER_TIME_LIMIT_SECONDS": 10,
    "MAX_ROOMS_ALLOWED": 10,
    "SOLVER_MAX_HALLWAY_SEGMENTS": 2,
    "MAX_LAYOUT_ALTERNATIVES": 3,
    "HALLWAY_WIDTH_MIN": 3,
    "HALLWAY_WIDTH_MAX": 4,
    "HALLWAY_MIN_TOTAL_LENGTH": 12,
    "HALLWAY_ROOM_WALL_MIN": 3,
    "HALLWAY_NETWORK_WALL_MIN": 3,
}

REQUIRED_FUNCTIONS = {
    "resolve_room_type": ["raw_type"],
    "get_room_bounds": ["room_type"],
    "get_min_room_area": ["room_type"],
    "get_p1_room_specs": ["rooms", "pins"],
}


def test_constants_present_with_agreed_values():
    for name, value in REQUIRED_CONSTANTS.items():
        assert hasattr(config, name), f"config.{name} was removed"
        assert getattr(config, name) == value, f"config.{name} changed"


def test_functions_present_with_same_parameters():
    for name, params in REQUIRED_FUNCTIONS.items():
        fn = getattr(config, name, None)
        assert callable(fn), f"config.{name} was removed"
        assert list(inspect.signature(fn).parameters) == params, f"config.{name} signature changed"


def test_get_room_bounds_shape():
    assert config.get_room_bounds("dining") == {
        "min_width": 12, "min_height": 12, "max_width": 20, "max_height": 20,
    }
    assert config.get_room_bounds("bathroom") == {
        "min_width": 5, "min_height": 7, "max_width": 8, "max_height": 10,
    }


def test_engine_style_import():
    # Exactly what P2's engine.py does.
    from floorplan.config import MAX_LAYOUT_ALTERNATIVES, get_room_bounds  # noqa: F401


def test_room_size_table_shape_used_by_engine():
    # engine.preferred_sizes reads ["preferred"]; get_room_bounds reads ["min"] / ["max"].
    for room_type in ("living", "kitchen", "bedroom", "bathroom"):
        entry = config.ROOM_SIZE_TABLE[room_type]
        assert {"min", "preferred", "max"} <= set(entry)
        assert all(len(entry[k]) == 2 for k in ("min", "preferred", "max"))


def test_engine_full_config_import():
    # The exact import block at the top of P2's engine.py.
    from floorplan.config import (  # noqa: F401
        CIRCULATION_FACTOR, MAX_LAYOUT_ALTERNATIVES, ROOM_SIZE_TABLE,
        SOLVER_TIME_LIMIT_SECONDS, get_room_bounds, resolve_room_type,
    )


def test_engine_build_output_call():
    # engine.build_output does FloorPlanOutput(layouts=layouts).model_dump() with these values.
    from floorplan.schema import FloorPlanOutput
    out = FloorPlanOutput(layouts=[{
        "score": 88.4,
        "rooms": [{"name": "Living", "type": "living", "x": 0, "y": 0, "w": 12, "h": 12}],
        "hallway_segments": [{"id": "hallway_1", "x": 0, "y": 12, "w": 12, "h": 3}],
        "doors": [{"between": ["outside", "Living"], "x": 6, "y": 0}],
        "windows": [],
        "messages": ["Living preference relaxed: could not fit in NE"],
    }]).model_dump()
    assert out["layouts"][0]["score"] == 88.4
