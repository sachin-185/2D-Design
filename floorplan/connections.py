"""Solver-side adjacency constraints.

The checker has an independent implementation in connections_check.py.
"""

HALLWAY = "hallway"
LEGACY_HALLWAY = "hallway_1"


def required_pairs(inp):
    """Return required room connections; 'hallway' means any hallway segment."""
    pairs = []
    living = [r["name"] for r in inp["rooms"] if r["type"] == "living"]

    for room in inp["rooms"]:
        if room["type"] in ("living", "bedroom", "bathroom"):
            pairs.append((room["name"], HALLWAY))

    if living:
        pairs.extend(
            (room["name"], living[0])
            for room in inp["rooms"]
            if room["type"] == "kitchen"
        )

    return pairs


def add_adjacency(model, A, B, door_min, W, L, tag, enforce=None):
    """Require A and B to share a wall of at least ``door_min`` feet.

    If ``enforce`` is a Boolean variable, adjacency is required only when it is
    true. This lets the solver express OR adjacency across optional hallway
    segments without requiring a room to touch every segment.
    """
    ways = [model.new_bool_var(f"{tag}_{i}") for i in range(4)]

    model.add(A["x"] + A["w"] == B["x"]).only_enforce_if(ways[0])
    model.add(B["x"] + B["w"] == A["x"]).only_enforce_if(ways[1])
    model.add(A["y"] + A["h"] == B["y"]).only_enforce_if(ways[2])
    model.add(B["y"] + B["h"] == A["y"]).only_enforce_if(ways[3])

    top = model.new_int_var(0, L, f"{tag}_top")
    bottom = model.new_int_var(0, L, f"{tag}_bottom")
    right = model.new_int_var(0, W, f"{tag}_right")
    left = model.new_int_var(0, W, f"{tag}_left")

    model.add_min_equality(top, [A["y"] + A["h"], B["y"] + B["h"]])
    model.add_max_equality(bottom, [A["y"], B["y"]])
    model.add_min_equality(right, [A["x"] + A["w"], B["x"] + B["w"]])
    model.add_max_equality(left, [A["x"], B["x"]])

    model.add(top - bottom >= door_min).only_enforce_if(ways[0])
    model.add(top - bottom >= door_min).only_enforce_if(ways[1])
    model.add(right - left >= door_min).only_enforce_if(ways[2])
    model.add(right - left >= door_min).only_enforce_if(ways[3])

    if enforce is None:
        model.add_bool_or(ways)
    else:
        model.add_bool_or(ways).only_enforce_if(enforce)
        for way in ways:
            model.add_implication(way, enforce)

    return ways
