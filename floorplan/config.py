"""
floorplan/config.py

Single source of truth for room dimensions,
grid resolution, and engine constants.

Shared by P1, P3 and P4.
"""

from typing import Dict, Tuple, Any, List, Optional


# 1. Authoritative Room Dimensions

ROOM_SIZE_TABLE: Dict[str, Dict[str, Tuple[int, int]]] = {
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
    "other": {
        "min": (6, 6),
        "preferred": (8, 8),
        "max": (10, 10),
    },
}


# 2. Minimum Room Areas

MIN_ROOM_AREA: Dict[str, int] = {
    room_type: dims["min"][0] * dims["min"][1]
    for room_type, dims in ROOM_SIZE_TABLE.items()
}


# 3. Secondary Room Type Aliases

ROOM_TYPE_ALIASES: Dict[str, str] = {
    "dining": "living",
    "utility": "other",
    "store": "other",
    "storage": "other",
    "study": "other",
    "laundry": "other",
}


# 4. Hallway and Door Constants

HALLWAY_WIDTH_MIN: int = 3
HALLWAY_WIDTH_MAX: int = 4
HALLWAY_MIN_TOTAL_LENGTH: int = 12

CIRCULATION_FACTOR: float = 0.15

MIN_DOOR_WALL_LENGTH: int = 3


# 5. Solver Constants

GRID_UNIT_FT: int = 1
SOLVER_TIME_LIMIT_SECONDS: int = 10
MAX_LAYOUT_ALTERNATIVES: int = 3
MAX_ROOMS_ALLOWED: int = 10


# 6. Helper Functions

def resolve_room_type(room_type: str) -> str:
    """Resolve aliases to their authoritative room type."""

    clean_type = room_type.strip().lower()

    return ROOM_TYPE_ALIASES.get(
        clean_type,
        clean_type if clean_type in ROOM_SIZE_TABLE else "other"
    )


def get_room_bounds(room_type: str) -> Dict[str, int]:
    """Return explicit width and height bounds for a room."""

    resolved = resolve_room_type(room_type)
    spec = ROOM_SIZE_TABLE[resolved]

    return {
        "min_width": spec["min"][0],
        "max_width": spec["max"][0],
        "min_height": spec["min"][1],
        "max_height": spec["max"][1],
    }


def get_p1_room_specs(
    rooms: List[Dict[str, Any]],
    pins: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Dict[str, int]]:
    """
    Convert room input into P1's expected room_specs format.
    Apply pinned dimensions where provided.
    """

    room_specs = {}

    for room in rooms:
        name = room["name"]
        room_type = room.get("type", "other")

        room_specs[name] = get_room_bounds(room_type)

    # Apply pinned dimension overrides
    if pins:
        for pin in pins:
            room_name = pin.get("room")

            if room_name in room_specs:

                if pin.get("width") is not None:
                    room_specs[room_name]["min_width"] = pin["width"]
                    room_specs[room_name]["max_width"] = pin["width"]

                if pin.get("height") is not None:
                    room_specs[room_name]["min_height"] = pin["height"]
                    room_specs[room_name]["max_height"] = pin["height"]

    return room_specs
