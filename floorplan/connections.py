"""Solver side of adjacency (P4): the rules we hand to the solver BEFORE a layout exists.

The checker side lives in connections_check.py. The two follow the same written rules
(connection_rules.md) but share no code, so a mistake cannot hide in both.

P1's model will call add_adjacency() once per pair from required_pairs().
A room here is a dict with OR-Tools variables under "x", "y", "w", "h".
"""

HALLWAY = "hallway_1"  # id of the single MVP hallway segment, agreed with P1


def required_pairs(inp):
    """Pairs of room names that must share a door-sized wall (see connection_rules.md)."""
    pairs = []
    living = [r["name"] for r in inp["rooms"] if r["type"] == "living"]
    for r in inp["rooms"]:
        if r["type"] in ("living", "bedroom", "bathroom"):
            pairs.append((r["name"], HALLWAY))
    if living:
        pairs += [(r["name"], living[0]) for r in inp["rooms"] if r["type"] == "kitchen"]
    return pairs


def add_adjacency(model, A, B, door_min, W, L, tag):
    """Force rooms A and B to touch, with a shared wall of at least door_min ft.

    Same idea as adjacency_toy.py: one true/false variable per direction, a touching rule that only
    applies for the chosen direction, and a minimum overlap length along the shared wall.
    tag must be unique per pair, because it names the helper variables.
    """
    way = [model.NewBoolVar(f"{tag}_{i}") for i in range(4)]
    model.Add(A["x"] + A["w"] == B["x"]).OnlyEnforceIf(way[0])  # A left of B
    model.Add(B["x"] + B["w"] == A["x"]).OnlyEnforceIf(way[1])  # A right of B
    model.Add(A["y"] + A["h"] == B["y"]).OnlyEnforceIf(way[2])  # A below B
    model.Add(B["y"] + B["h"] == A["y"]).OnlyEnforceIf(way[3])  # A above B
    top = model.NewIntVar(0, L, f"{tag}_top")
    bottom = model.NewIntVar(0, L, f"{tag}_bottom")
    right = model.NewIntVar(0, W, f"{tag}_right")
    left = model.NewIntVar(0, W, f"{tag}_left")
    model.AddMinEquality(top, [A["y"] + A["h"], B["y"] + B["h"]])
    model.AddMaxEquality(bottom, [A["y"], B["y"]])
    model.AddMinEquality(right, [A["x"] + A["w"], B["x"] + B["w"]])
    model.AddMaxEquality(left, [A["x"], B["x"]])
    model.Add(top - bottom >= door_min).OnlyEnforceIf(way[0])
    model.Add(top - bottom >= door_min).OnlyEnforceIf(way[1])
    model.Add(right - left >= door_min).OnlyEnforceIf(way[2])
    model.Add(right - left >= door_min).OnlyEnforceIf(way[3])
    model.AddBoolOr(way)
