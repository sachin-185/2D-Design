"""Independent layout checks (P4).

Rules:
- Do not import anything from the solver. If the solver has a bug, the
  checker must not share it.
- Every check returns a list of violations. An empty list means pass.
- Each violation is a dict: {"code", "message", "rooms"}.

Layout format:
  layout = {
      "rooms": [{"name": "kitchen", "x": 0, "y": 0, "w": 10, "h": 10}, ...],
      "hallway_segments": [
          {"id": "hallway_1", "x": 0, "y": 0, "w": 12, "h": 3}, ...
      ]
  }
  A legacy singular "hallway" rectangle is also accepted.
  Coordinates are in feet, origin at the bottom-left of the BUILDABLE area
  (plot minus setbacks). If P3 changes the format, only all_rooms() should
  need to change.
"""

# Room sizes agreed with P3 (her config.py, confirmed 2026-11-05).
# This is the checker's own copy on purpose: if config.py has a wrong number,
# the solver uses it but the checker does not, so H2 still catches the mistake.
# Each entry: (min [w, h], max [w, h]) in feet.
BASE_SIZES = {
    "living": ([12, 12], [20, 20]),
    "kitchen": ([8, 8], [12, 12]),
    "bedroom": ([10, 10], [16, 16]),
    "bathroom": ([5, 7], [8, 10]),
}

# Secondary room types use the size limits of a base type.
# Only sizes are shared: the connection rules still see the original type.
SIZE_ALIASES = {
    "dining": "living",
    "study": "living",
    "utility": "kitchen",
    "store": "kitchen",
    "storage": "kitchen",
    "laundry": "kitchen",
}

SIZE_TABLE = {
    **BASE_SIZES,
    **{alias: (list(BASE_SIZES[base][0]), list(BASE_SIZES[base][1]))
       for alias, base in SIZE_ALIASES.items()},
}


def violation(code, message, rooms, severity="error"):
    return {"code": code, "message": message, "rooms": list(rooms), "severity": severity}


def check_input(inp):
    """I1: the input is usable by the other checks. Reports bad input instead of crashing.

    P3's schema already limits these values, but the checker can be called without the schema.
    Room names "hallway" and "hallway_<number>" are reserved: they are the hallway's names.
    attached_to must name a room in the input.
    """
    found = []
    if inp.get("entrance") not in ("N", "E", "S", "W"):
        found.append(violation("I1", f"entrance must be N, E, S or W, got {inp.get('entrance')!r}", []))
    if inp.get("north", "up") not in ("up", "down", "left", "right"):
        found.append(violation("I1", f"north must be up, down, left or right, got {inp.get('north')!r}", []))
    rooms = inp.get("rooms") or []
    if not rooms:
        found.append(violation("I1", "the input has no rooms", []))
    seen = set()
    for room in rooms:
        name = room.get("name")
        if name == "hallway" or (isinstance(name, str) and name.startswith("hallway_") and name[8:].isdigit()):
            found.append(violation("I1", f"room name '{name}' is reserved for the hallway", [name]))
        if name in seen:
            found.append(violation("I1", f"two rooms are named '{name}'", [name]))
        seen.add(name)
    names = [room.get("name") for room in rooms]
    for room in rooms:
        target = room.get("attached_to")
        if target and target not in names:
            found.append(violation(
                "I1", f"{room.get('name')} is attached to '{target}', which is not in the input",
                [room.get("name"), target]))
    return found


def buildable_area(inp):
    """Usable (width, length) after setbacks. Setbacks default to 0."""
    plot_w, plot_l = inp["plot"]
    s = inp.get("setbacks", {})
    width = plot_w - s.get("left", 0) - s.get("right", 0)
    length = plot_l - s.get("front", 0) - s.get("back", 0)
    return width, length


HALLWAY_ID = "hallway_1"  # first hallway segment ID; additional segments are numbered


def hallway_segments(layout):
    """Return all hallway rectangles as named segments.

    Supports the current hallway_segments list and the legacy singular hallway field.
    """
    segments = layout.get("hallway_segments")
    if segments is None:
        one = layout.get("hallway")
        segments = [one] if one else []
    return [{**s, "name": s.get("id") or f"hallway_{i + 1}"} for i, s in enumerate(segments)]


def all_rooms(layout):
    """Rooms plus the hallway segments as one list. The only place that reads the format."""
    return list(layout["rooms"]) + hallway_segments(layout)


def check_inside_plot(inp, layout):
    """H1: every room stays inside the buildable area."""
    width, length = buildable_area(inp)
    found = []
    for r in all_rooms(layout):
        if r["x"] < 0 or r["y"] < 0 or r["x"] + r["w"] > width or r["y"] + r["h"] > length:
            found.append(violation(
                "H1",
                f"{r['name']} sticks out of the buildable area ({width} x {length} ft)",
                [r["name"]],
            ))
    return found


def check_no_overlap(layout):
    """H3: no two rooms share any floor area. Touching edges is fine."""
    rooms = all_rooms(layout)
    found = []
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            a, b = rooms[i], rooms[j]
            overlaps = (
                a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]
            )
            if overlaps:
                found.append(violation(
                    "H3",
                    f"{a['name']} and {b['name']} overlap",
                    [a["name"], b["name"]],
                ))
    return found


def check_size_limits(inp, layout, size_table=SIZE_TABLE):
    """H2: each room is within its min and max size, and pinned sizes hold.

    A room may be turned 90 degrees, so sides are compared shortest to
    shortest and longest to longest. The hallway is not checked here.
    """
    found = []
    types = {r["name"]: r for r in inp["rooms"]}
    for r in layout["rooms"]:
        spec = types.get(r["name"])
        if spec is None:
            found.append(violation("H2", f"{r['name']} is not in the input", [r["name"]]))
            continue
        if spec["type"] not in size_table:
            found.append(violation(
                "H2", f"no size rule for room type '{spec['type']}' ({r['name']})", [r["name"]]))
            continue
        table_min, table_max = size_table[spec["type"]]
        lo = sorted(spec.get("min", table_min))
        hi = sorted(spec.get("max", table_max))
        sides = sorted([r["w"], r["h"]])
        if sides[0] < lo[0] or sides[1] < lo[1]:
            found.append(violation(
                "H2",
                f"{r['name']} is {r['w']} x {r['h']} ft, below its minimum of {lo[0]} x {lo[1]} ft",
                [r["name"]],
            ))
        if sides[0] > hi[0] or sides[1] > hi[1]:
            found.append(violation(
                "H2",
                f"{r['name']} is {r['w']} x {r['h']} ft, above its maximum of {hi[0]} x {hi[1]} ft",
                [r["name"]],
            ))
    for pin in inp.get("pins", []):
        room = next((r for r in layout["rooms"] if r["name"] == pin["room"]), None)
        if room is None:
            found.append(violation("H2", f"pinned room {pin['room']} is missing", [pin["room"]]))
            continue
        if "width" in pin and room["w"] != pin["width"]:
            found.append(violation(
                "H2", f"{pin['room']} width is {room['w']}, pinned to {pin['width']}", [pin["room"]]))
        if "height" in pin and room["h"] != pin["height"]:
            found.append(violation(
                "H2", f"{pin['room']} height is {room['h']}, pinned to {pin['height']}", [pin["room"]]))
    return found


def validate(inp, layout, size_table=SIZE_TABLE):
    """Run every check and return all violations."""
    return (
        check_inside_plot(inp, layout)
        + check_no_overlap(layout)
        + check_size_limits(inp, layout, size_table)
    )