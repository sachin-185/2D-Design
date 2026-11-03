"""Connection checks (P4): who touches whom, can you walk everywhere, no gaps.

Uses the same layout format and helpers as validator.py. Does not import the solver.
"""
from collections import deque
import math
from .validator import all_rooms, buildable_area, hallway_segments, violation

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
    severity = "warning" if diff > 0 else "error"
    return [violation("H4", f"rooms cover {total} sq ft of {width * length} sq ft ({abs(diff)} sq ft {word})", [], severity)]


HALLWAY = "hallway"  # any segment in the connected hallway network


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


# Room types that may use any living room instead of the hallway (team decision, open decision 8).
LIVING_ALTERNATIVE_TYPES = ("bedroom", "bathroom")


def longest_shared_wall(room, others):
    """The longest wall room shares with any rectangle in others. 0 when others is empty."""
    return max((shared_wall_length(room, other) for other in others), default=0)


def check_hallway_requirement(name, room_type, rooms, halls, living_rooms, door_min=DOOR_MIN):
    """H6 for one (room, "hallway") pair from expected_connections.

    - Bedroom and bathroom: any hallway segment OR any living room is enough.
    - Living room: must touch a hallway segment only when the layout has one.

    The solver side (required_pairs in connections.py) still uses the strict hallway rule.
    P1 will update it later; expected_connections keeps the same pairs so the two lists still agree.
    """
    if name not in rooms:
        return [violation("H6", f"{name} is missing from the layout", [name])]
    room = rooms[name]
    hall_names = [hall["name"] for hall in halls]

    if room_type in LIVING_ALTERNATIVE_TYPES:
        hall_wall = longest_shared_wall(room, halls)
        living_wall = longest_shared_wall(room, living_rooms)
        if max(hall_wall, living_wall) >= door_min:
            return []
        hall_note = "" if halls else " (the layout has no hallway)"
        living_note = "" if living_rooms else " (the layout has no living room)"
        return [violation(
            "H6",
            f"{name} shares {hall_wall} ft with the hallway network{hall_note} and {living_wall} ft "
            f"with a living room{living_note}; needs {door_min} ft with one of them",
            [name] + hall_names + [living["name"] for living in living_rooms],
        )]

    if not halls:  # no hallway in the layout: nothing to touch
        return []
    hall_wall = longest_shared_wall(room, halls)
    if hall_wall >= door_min:
        return []
    return [violation(
        "H6", f"{name} shares {hall_wall} ft with the hallway network; needs {door_min} ft", [name] + hall_names)]


def check_required_connections(inp, layout, door_min=DOOR_MIN):
    """H6: required rooms connect to the hallway (or, for bedrooms and bathrooms, a living room)
    and to their paired room."""
    rooms = {r["name"]: r for r in layout["rooms"]}
    halls = hallway_segments(layout)
    types = {r["name"]: r["type"] for r in inp["rooms"]}
    living_rooms = [rooms[name] for name, kind in types.items() if kind == "living" and name in rooms]
    rooms.update({hall["name"]: hall for hall in halls})
    found = []

    for a, b in expected_connections(inp):
        if b == HALLWAY:
            found += check_hallway_requirement(a, types.get(a), rooms, halls, living_rooms, door_min)
            continue

        missing = [name for name in (a, b) if name not in rooms]
        if missing:
            found.append(violation("H6", f"{missing[0]} is missing from the layout, so {a} and {b} cannot connect", [a, b]))
            continue
        length = shared_wall_length(rooms[a], rooms[b])
        if length < door_min:
            found.append(violation("H6", f"{a} and {b} share {length} ft of wall, need {door_min} ft", [a, b]))
    return found


def check_hallway_connectivity(layout, door_min=DOOR_MIN):
    """HW2: hallway segments form one connected group without using rooms."""
    halls = hallway_segments(layout)
    if len(halls) <= 1:
        return []

    graph = {hall["name"]: set() for hall in halls}
    for i, first in enumerate(halls):
        for second in halls[i + 1:]:
            if shared_wall_length(first, second) >= door_min:
                graph[first["name"]].add(second["name"])
                graph[second["name"]].add(first["name"])

    seen = reachable_rooms(graph, halls[0]["name"])
    missing = sorted(set(graph) - seen)
    if missing:
        return [violation("HW2", f"Hallway segments are disconnected: {', '.join(missing)}", missing)]
    return []


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
    """HW1: each segment is 3-4 ft wide; total long-side length is >= 12 ft."""
    halls = hallway_segments(layout)
    found = []
    total_long_side = 0
    for hall in halls:
        short, long_ = sorted([hall["w"], hall["h"]])
        total_long_side += long_
        if not HALLWAY_WIDTH[0] <= short <= HALLWAY_WIDTH[1]:
            found.append(violation(
                "HW1", f"{hall['name']} is {short} ft wide, must be {HALLWAY_WIDTH[0]} to {HALLWAY_WIDTH[1]} ft",
                [hall["name"]],
            ))
    if halls and total_long_side < HALLWAY_MIN_LENGTH:
        found.append(violation(
            "HW1", f"Hallway network has {total_long_side} ft total length; needs at least {HALLWAY_MIN_LENGTH} ft",
            [hall["name"] for hall in halls],
        ))
    return found


def check_no_5x5_hallway_square(layout):
    """
    HW3: Reject a hallway network if any complete 5x5 ft
    axis-aligned square fits inside the combined hallway area.

    Checks all hallway segments together, not individually.

    Assumes hallway coordinates and dimensions use whole feet.
    """
    halls = hallway_segments(layout)

    if not halls:
        return []

    # Find the overall hallway bounding rectangle.
    min_x = min(hall["x"] for hall in halls)
    min_y = min(hall["y"] for hall in halls)

    max_x = max(hall["x"] + hall["w"] for hall in halls)
    max_y = max(hall["y"] + hall["h"] for hall in halls)

    # Check every possible 5x5 square on the 1 ft coordinate grid.
    for start_x in range(math.floor(min_x), math.floor(max_x) - 4):
        for start_y in range(math.floor(min_y), math.floor(max_y) - 4):

            square_is_covered = True

            # A 5x5 square contains 25 one-foot cells.
            for dx in range(5):
                for dy in range(5):

                    # Test the centre of each one-foot cell.
                    cell_x = start_x + dx + 0.5
                    cell_y = start_y + dy + 0.5

                    covered = any(
                        hall["x"] <= cell_x < hall["x"] + hall["w"]
                        and
                        hall["y"] <= cell_y < hall["y"] + hall["h"]
                        for hall in halls
                    )

                    if not covered:
                        square_is_covered = False
                        break

                if not square_is_covered:
                    break

            if square_is_covered:
                return [
                    violation(
                        "HW3",
                        (
                            "Hallway network contains a complete "
                            f"5x5 ft square at ({start_x}, {start_y}). "
                            "Hallway area must not accommodate a 5x5 ft square."
                        ),
                        [hall["name"] for hall in halls],
                    )
                ]

    return []


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
