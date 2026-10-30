"""Connection checks (P4): who touches whom, can you walk everywhere, no gaps.

Uses the same layout format and helpers as validator.py. Does not import the solver.
"""
from collections import deque

from .validator import HALLWAY_ID, all_rooms, buildable_area, hallway_segments, violation

DOOR_MIN = 3  # ft, see connection_rules.md


def shared_wall_length(a, b):
    """Length in ft of the wall two rooms share. 0 if they only touch at a corner or not at all."""
    best = 0
    if a["x"] + a["w"] == b["x"] or b["x"] + b["w"] == a["x"]:  # side by side
        best = max(best, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
    if a["y"] + a["h"] == b["y"] or b["y"] + b["h"] == a["y"]:  # one above the other
        best = max(best, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
    return max(best, 0)


def build_graph(layout, door_min=DOOR_MIN):
    """Rooms are nodes. Two rooms are linked if they share a wall of at least door_min ft."""
    rooms = all_rooms(layout)
    graph = {r["name"]: set() for r in rooms}
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            if shared_wall_length(rooms[i], rooms[j]) >= door_min:
                graph[rooms[i]["name"]].add(rooms[j]["name"])
                graph[rooms[j]["name"]].add(rooms[i]["name"])
    return graph


def reachable_rooms(graph, start):
    """Breadth-first search: every room you can walk to from start."""
    seen, queue = {start}, deque([start])
    while queue:
        room = queue.popleft()
        for nxt in graph[room]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def check_reachability(layout, entrance_room="living", door_min=DOOR_MIN):
    """F5: every room can be reached from the entrance room."""
    graph = build_graph(layout, door_min)
    if entrance_room not in graph:
        return [violation("F5", f"entrance room '{entrance_room}' is not in the layout", [entrance_room])]
    seen = reachable_rooms(graph, entrance_room)
    return [
        violation("F5", f"{name} cannot be reached from {entrance_room}", [name])
        for name in sorted(graph) if name not in seen
    ]


def check_no_gaps(inp, layout):
    """H4: room areas (hallway included) add up to the buildable area exactly.

    Run check_no_overlap too: overlap would hide a gap elsewhere.
    """
    width, length = buildable_area(inp)
    total = sum(r["w"] * r["h"] for r in all_rooms(layout))
    if total == width * length:
        return []
    diff = width * length - total
    word = "unused" if diff > 0 else "extra"
    return [violation("H4", f"rooms cover {total} sq ft of {width * length} sq ft ({abs(diff)} sq ft {word})", [])]


HALLWAY = HALLWAY_ID  # the single MVP hallway segment, hallway_1


def expected_connections(inp):
    """Pairs that must share a door-sized wall, written from connection_rules.md.

    Deliberately NOT shared with connections.py (the solver side), so a mistake in one cannot hide
    in the other. A test checks that the two lists agree.
    """
    names_by_type = {}
    for r in inp["rooms"]:
        names_by_type.setdefault(r["type"], []).append(r["name"])
    pairs = []
    for room_type in ("living", "bedroom", "bathroom"):
        pairs += [(name, HALLWAY) for name in names_by_type.get(room_type, [])]
    living = names_by_type.get("living", [])
    if living:  # the first living room is the one the kitchen must touch
        pairs += [(kitchen, living[0]) for kitchen in names_by_type.get("kitchen", [])]
    return pairs


def check_required_connections(inp, layout, door_min=DOOR_MIN):
    """H6: every pair that must connect shares a wall of at least door_min ft."""
    rooms = {r["name"]: r for r in all_rooms(layout)}
    found = []
    for a, b in expected_connections(inp):
        missing = [n for n in (a, b) if n not in rooms]
        if missing:
            found.append(violation("H6", f"{missing[0]} is missing from the layout, so {a} and {b} cannot connect", [a, b]))
            continue
        length = shared_wall_length(rooms[a], rooms[b])
        if length < door_min:
            found.append(violation("H6", f"{a} and {b} share {length} ft of wall, need {door_min} ft", [a, b]))
    return found


def check_bedroom_through_bedroom(inp, layout, entrance_room, door_min=DOOR_MIN):
    """F1: a bedroom that can only be reached by walking through another bedroom.

    You may walk INTO a bedroom, but not THROUGH it. Needs only the room map, not door positions.
    """
    types = {r["name"]: r["type"] for r in inp["rooms"]}
    graph = build_graph(layout, door_min)
    if entrance_room not in graph:
        return []  # check_reachability already reports this
    everyone = reachable_rooms(graph, entrance_room)
    seen, queue = {entrance_room}, deque([entrance_room])
    while queue:
        room = queue.popleft()
        if types.get(room) == "bedroom" and room != entrance_room:
            continue  # arrived in a bedroom: do not continue through it
        for nxt in graph[room]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return [
        violation("F1", f"{name} can only be reached through another bedroom", [name])
        for name in sorted(everyone - seen) if types.get(name) == "bedroom"
    ]


# --- hallway shape and entrance wall (rules written in connection_rules.md) ---------------------

HALLWAY_WIDTH = (3, 4)    # ft, the short side of the hallway
HALLWAY_MIN_LENGTH = 12   # ft, the long side of the hallway

# Which edge of the DRAWING the real-world entrance side sits on, given where north points.
# An independent copy: basic_layout.py has its own, so a mistake cannot hide in both.
ENTRANCE_EDGE = {
    "up":    {"N": "top", "S": "bottom", "E": "right", "W": "left"},
    "down":  {"N": "bottom", "S": "top", "E": "left", "W": "right"},
    "left":  {"N": "left", "S": "right", "E": "top", "W": "bottom"},
    "right": {"N": "right", "S": "left", "E": "bottom", "W": "top"},
}


def check_hallway_shape(layout):
    """HW1: each hallway segment is 3 to 4 ft wide and at least 12 ft long (placeholder numbers)."""
    found = []
    for hall in hallway_segments(layout):
        short, long_ = sorted([hall["w"], hall["h"]])
        if not HALLWAY_WIDTH[0] <= short <= HALLWAY_WIDTH[1]:
            found.append(violation(
                "HW1", f"{hall['name']} is {short} ft wide, must be {HALLWAY_WIDTH[0]} to {HALLWAY_WIDTH[1]} ft",
                [hall["name"]]))
        if long_ < HALLWAY_MIN_LENGTH:
            found.append(violation(
                "HW1", f"{hall['name']} is only {long_} ft long, must be at least {HALLWAY_MIN_LENGTH} ft",
                [hall["name"]]))
    return found


def check_entrance_wall(inp, layout):
    """E1: the living room (the entrance room) touches the wall where the entrance is."""
    living = next((r["name"] for r in inp["rooms"] if r["type"] == "living"), None)
    room = next((r for r in layout["rooms"] if r["name"] == living), None)
    if room is None:
        return []  # no living room to check
    width, length = buildable_area(inp)
    edge = ENTRANCE_EDGE[inp.get("north", "up")][inp["entrance"]]
    touches = {
        "bottom": room["y"] == 0,
        "top": room["y"] + room["h"] == length,
        "left": room["x"] == 0,
        "right": room["x"] + room["w"] == width,
    }[edge]
    if touches:
        return []
    return [violation(
        "E1", f"{living} must touch the {edge} edge of the plot (entrance side {inp['entrance']}), but it does not",
        [living])]
