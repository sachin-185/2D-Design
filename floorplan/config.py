

ROOM_SIZE_TABLE = {
    "living": {
        "name": "Living",
        "min": (12, 12),
        "preferred": (15, 16),
        "max": (20, 20),
        "outer_wall": True,
    },
    "kitchen": {
        "name": "Kitchen",
        "min": (8, 8),
        "preferred": (10, 10),
        "max": (12, 12),
        "outer_wall": True,
    },
    "bedroom": {
        "name": "Bedroom",
        "min": (10, 10),
        "preferred": (12, 12),
        "max": (16, 16),
        "outer_wall": True,
    },
    "bathroom": {
        "name": "Bathroom",
        "min": (5, 7),
        "preferred": (6, 8),
        "max": (8, 10),
        "outer_wall": False,
    },
    "dining": {
        "name": "Dining",
        "min": (10, 10),
        "preferred": (12, 12),
        "max": (14, 16),
        "outer_wall": False,
    },
    "office": {
        "name": "Office",
        "min": (8, 8),
        "preferred": (10, 10),
        "max": (12, 14),
        "outer_wall": True,
    },
}

DEFAULT_SETBACKS = {
    "front": 5,
    "back": 3,
    "left": 3,
    "right": 3,
}
