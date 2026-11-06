"""
floorplan/config.py
Authoritative room size configuration, alias normalization, and P1 solver adapter.
Owner: P3 (Input and Glue)
"""

from typing import Dict, Any, List, Optional, Tuple

# Grid & Solver Constants
GRID_UNIT_FT: int = 1
CIRCULATION_FACTOR: float = 0.15
SOLVER_TIME_LIMIT_SECONDS: int = 10
MAX_ROOMS_ALLOWED: int = 10
SOLVER_MAX_HALLWAY_SEGMENTS: int = 2
MAX_LAYOUT_ALTERNATIVES: int = 3

# Hallway standard dimensions matching geometry.py
HALLWAY_WIDTH_MIN: int = 3
HALLWAY_WIDTH_MAX: int = 4
HALLWAY_MIN_TOTAL_LENGTH: int = 12
HALLWAY_ROOM_WALL_MIN: int = 3
HALLWAY_NETWORK_WALL_MIN: int = 3

# 4 Canonical Room Types
ROOM_SIZE_TABLE: Dict[str, Dict[str, Any]] = {
    "living": {
        "min": (12, 12),
        "preferred": (15, 16),
        "max": (20, 20),
    },
    "kitchen": {
        "min": (8, 8),
        "preferred": (10, 10),
        "max": (12, 12),
    },
    "bedroom": {
        "min": (10, 10),
        "preferred": (12, 12),
        "max": (16, 16),
    },
    "bathroom": {
        "min": (5, 7),
        "preferred": (6, 8),
        "max": (8, 10),
    },
}

# Normalization mapping: secondary space aliases -> 4 canonical types
ROOM_TYPE_ALIASES: Dict[str, str] = {
    "dining": "living",
    "study": "living",
    "utility": "kitchen",
    "store": "kitchen",
    "storage": "kitchen",
    "laundry": "kitchen",
}


def resolve_room_type(raw_type: str) -> str:
    """Normalizes any incoming alias to one of the 4 canonical types."""
    canonical = raw_type.lower().strip()
    return ROOM_TYPE_ALIASES.get(canonical, canonical)


def get_room_bounds(room_type: str) -> Dict[str, int]:
    """Returns min/max dimensions for a room type or alias for engine/solver lookups."""
    canonical = resolve_room_type(room_type)
    bounds = ROOM_SIZE_TABLE[canonical]
    return {
        "min_width": bounds["min"][0],
        "min_height": bounds["min"][1],
        "max_width": bounds["max"][0],
        "max_height": bounds["max"][1],
    }


def get_min_room_area(room_type: str) -> int:
    """Helper returning minimum square footage for a room type."""
    canonical = resolve_room_type(room_type)
    min_w, min_h = ROOM_SIZE_TABLE[canonical]["min"]
    return min_w * min_h


def get_p1_room_specs(
    rooms: List[Dict[str, Any]], 
    pins: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Dict[str, int]]:
    """Translates P3 room payloads into the dictionary structure strictly demanded by geometry.py."""
    pin_lookup = {p["room"]: p for p in (pins or [])}
    p1_specs: Dict[str, Dict[str, int]] = {}

    for r in rooms:
        bounds = get_room_bounds(r["type"])
        pin = pin_lookup.get(r["name"], {})

        min_w, min_h = bounds["min_width"], bounds["min_height"]
        max_w, max_h = bounds["max_width"], bounds["max_height"]

        p1_specs[r["name"]] = {
            "min_width": pin.get("width") or min_w,
            "max_width": pin.get("width") or max_w,
            "min_height": pin.get("height") or min_h,
            "max_height": pin.get("height") or max_h,
        }

    return p1_specs