"""The whole engine in one call: input -> 3 checked layouts -> output JSON.

    result = solve_request(inp)
    result = edit_layout(inp, result["layouts"][0], {"bedroom": {"width": 14}}, lock=["living"])

Steps (MVP plan, Engine Steps): check the input (P4), read the size table (P3), solve variants with
P1's geometry and P2's preferences, place doors, then have P4's independent checker confirm every
layout before it is returned. A layout the checker rejects is dropped, never returned.

Result: {"status", "layouts", "messages"}. status is one of:
    valid       at least one layout passed the checker (warnings are allowed)
    infeasible  the input cannot be satisfied; messages say by how much
    conflict    'must' zones cannot hold; "conflict_rooms" names the rooms
    invalid     the input itself cannot be used, or no layout passed the checker
    timeout     the solver found nothing within the time limit
"""
from typing import Any, Dict, List, Optional

from floorplan.config import (
    CIRCULATION_FACTOR,
    MAX_LAYOUT_ALTERNATIVES,
    ROOM_SIZE_TABLE,
    SOLVER_TIME_LIMIT_SECONDS,
    get_room_bounds,
    resolve_room_type,
)
from floorplan.connections import HALLWAY, required_pairs
from floorplan.geometry import ENTRANCE_EDGE, calculate_buildable_area
from floorplan.input_adapter import build_preference_arguments, build_no_hallway_arguments
from floorplan.preferences import (
    ARCHETYPES,
    DOOR_MIN,
    generate_variants,
    solve_with_preferences,
    to_drawing_zone,
    zone_contains,
)
from floorplan.schema import FloorPlanOutput
from floorplan.validator import check_input
from validate_all import adapt_solver_result, errors_only, validate_all, warnings_only

OUTSIDE = "outside"  # the far side of the main door
PROBE_SECONDS = 5    # time limit for yes/no feasibility questions

# Hallway slots searched. Two allow an L shape and are proven impossible in under a second when no
# plan exists (t20); at three slots the solver cannot decide that within any practical limit.
MAX_HALLWAY_SEGMENTS = 2

# Below this share of the plot the rooms cannot make a sensible plan even at maximum size, so the
# plot is reported as too large (t07) instead of drawing a few rooms in an empty site.
# Placeholder until the team settles open decision 7 in connection_rules.md.
MIN_REACHABLE_COVERAGE = 0.60


def room_size_table(inp: Dict[str, Any]) -> Dict[str, Any]:
    """P3's config in the (min, max) shape the adapter and the checker read, for the types in this input."""
    table = {}
    for room in inp["rooms"]:
        bounds = get_room_bounds(room["type"])
        table[room["type"]] = (
            [bounds["min_width"], bounds["min_height"]],
            [bounds["max_width"], bounds["max_height"]],
        )
    return table


def preferred_sizes(inp: Dict[str, Any]) -> Dict[str, Any]:
    return {room["type"]: ROOM_SIZE_TABLE[resolve_room_type(room["type"])]["preferred"] for room in inp["rooms"]}


def check_area(args: Dict[str, Any]) -> Optional[str]:
    """Quick checks before solving: too small with walking space (plan step 3), or far too large."""
    area = calculate_buildable_area(args["plot_width"], args["plot_height"], args["setbacks"])
    total = area["width"] * area["depth"]
    specs = args["room_specs"].values()

    needed = sum(s["min_width"] * s["min_height"] for s in specs)
    with_walking = needed * (1 + CIRCULATION_FACTOR)
    if with_walking > total:
        return (f"Plot too small: the rooms need {needed} sq ft plus {CIRCULATION_FACTOR:.0%} walking space "
                f"({with_walking:.0f} sq ft), but the buildable area is {total} sq ft. "
                f"Short by {with_walking - total:.0f} sq ft.")

    corridor = 4 * max(area["width"], area["depth"])
    reachable = sum(s["max_width"] * s["max_height"] for s in specs) + corridor
    if reachable < MIN_REACHABLE_COVERAGE * total:
        return (f"Plot too large: at maximum size the rooms and hallway cover at most {reachable} of "
                f"{total} sq ft. Add rooms or reduce the plot.")
    return None


# --- doors ---------------------------------------------------------------------------------------

def shared_wall(a: Dict[str, int], b: Dict[str, int]):
    """The wall two rectangles share as ((x1, y1), (x2, y2)), or None if shorter than a door."""
    for ax, bx in ((a["x"] + a["w"], b["x"]), (b["x"] + b["w"], a["x"])):
        if ax == bx:
            low, high = max(a["y"], b["y"]), min(a["y"] + a["h"], b["y"] + b["h"])
            if high - low >= DOOR_MIN:
                return (ax, low), (ax, high)
    for ay, by in ((a["y"] + a["h"], b["y"]), (b["y"] + b["h"], a["y"])):
        if ay == by:
            low, high = max(a["x"], b["x"]), min(a["x"] + a["w"], b["x"] + b["w"])
            if high - low >= DOOR_MIN:
                return (low, ay), (high, ay)
    return None


def wall_length(wall) -> int:
    (x1, y1), (x2, y2) = wall
    return (x2 - x1) + (y2 - y1)


def _half_feet(value):
    """A whole number stays an int; a half foot (e.g. 18.5) stays exact."""
    return int(value) if value == int(value) else value


def wall_middle(wall):
    """Exact middle of a wall: where the door goes. On a 3 ft wall from 17 to 20 that is 18.5, so the
    3 ft door fills the wall exactly (rounding to 18 made it stick out half a foot past the wall)."""
    (x1, y1), (x2, y2) = wall
    return _half_feet((x1 + x2) / 2), _half_feet((y1 + y2) / 2)


def entrance_wall(inp: Dict[str, Any], room: Dict[str, int], width: int, depth: int):
    """The part of a room's outline on the entrance edge of the buildable area, or None."""
    edge = ENTRANCE_EDGE[inp.get("north", "up")][inp["entrance"]]
    x, y, w, h = room["x"], room["y"], room["w"], room["h"]
    if edge == "bottom" and y == 0:
        return (x, 0), (x + w, 0)
    if edge == "top" and y + h == depth:
        return (x, depth), (x + w, depth)
    if edge == "left" and x == 0:
        return (0, y), (0, y + h)
    if edge == "right" and x + w == width:
        return (width, y), (width, y + h)
    return None


def place_doors(inp: Dict[str, Any], layout: Dict[str, Any], width: int, depth: int) -> List[Dict[str, Any]]:
    """One door in the middle of each required shared wall, plus the main door.

    Stopgap for plan step 9 so the output is complete: F2 to F4 are not checked until P4 and P5 settle
    door rules. Rooms with no required partner, and bedrooms in a layout with no hallway, take the
    longest wall they share with a hallway segment or the living room.
    """
    rooms = {r["name"]: r for r in layout["rooms"]}
    halls = layout.get("hallway_segments", [])
    living = next((r["name"] for r in inp["rooms"] if r["type"] == "living"), None)

    def best_way_out(name):
        """(other side name, wall) with the longest shared wall, or None."""
        options = [(h["id"], shared_wall(rooms[name], h)) for h in halls]
        if living and living != name:
            options.append((living, shared_wall(rooms[name], rooms[living])))
        options = [option for option in options if option[1]]
        return max(options, key=lambda option: wall_length(option[1]), default=None)

    doors = []

    def add(a, b, wall):
        x, y = wall_middle(wall)
        doors.append({"between": [a, b], "x": x, "y": y})

    placed = set()
    for a, b in required_pairs(inp):
        found = best_way_out(a) if b == HALLWAY else (b, shared_wall(rooms[a], rooms[b]))
        if found and found[1]:
            add(a, found[0], found[1])
            placed.add(a)

    for room in inp["rooms"]:
        if room["name"] not in placed and room["name"] != living:
            found = best_way_out(room["name"])
            if found:
                add(room["name"], found[0], found[1])

    # A hallway network needs doors to itself only where segments meet, and those are open passages.
    if living:
        wall = entrance_wall(inp, rooms[living], width, depth)
        if wall:
            add(OUTSIDE, living, wall)
    return doors


# --- turning a solver result into checked output ---------------------------------------------------

def relaxed_preferences(inp: Dict[str, Any], variant: Dict[str, Any]) -> List[str]:
    """Which 'try' zones this layout could not honour, in the plan's own wording."""
    notes = []
    for room in inp["rooms"]:
        if room.get("zone") and room.get("zone_mode", "try") == "try":
            cell = to_drawing_zone(room["zone"], inp.get("north", "up"))
            placed = variant["rooms"][room["name"]]
            if not zone_contains(placed, cell, variant["buildable_width"], variant["buildable_depth"]):
                notes.append(f"{room['name']} preference relaxed: could not fit in {room['zone']}")
    return notes


def checked_layout(inp: Dict[str, Any], variant: Dict[str, Any], table: Dict[str, Any]):
    """(output layout, errors): runs P4's checker, which shares no code with the solver."""
    adapted = adapt_solver_result(variant)
    problems = validate_all(inp, adapted, size_table=table)
    errors = errors_only(problems)
    if errors:
        return None, errors

    types = {r["name"]: r["type"] for r in inp["rooms"]}
    width, depth = variant["buildable_width"], variant["buildable_depth"]
    messages = relaxed_preferences(inp, variant) + [p["message"] for p in warnings_only(problems)]
    segments = variant.get("hallway_segments", [])
    if not segments:
        messages.append("This layout has no hallway: rooms open off the living room.")

    layout = {
        "score": variant["score"],
        "rooms": [
            {"name": name, "type": types[name],  # the user's own type, e.g. dining (P3 contract)
             "x": room["x"], "y": room["y"], "w": room["width"], "h": room["height"]}
            for name, room in variant["rooms"].items()
        ],
        "hallway_segments": [{key: s[key] for key in ("id", "x", "y", "w", "h")} for s in segments],
        "doors": [],
        "windows": [],
        "messages": messages,
    }
    layout["doors"] = place_doors(inp, layout, width, depth)
    return layout, []


def build_output(inp, variants, table) -> Dict[str, Any]:
    """Check every variant and shape the survivors with P3's output schema."""
    layouts, extras, messages = [], [], []
    for variant in variants:
        layout, errors = checked_layout(inp, variant, table)
        if errors:
            messages.append("Dropped a layout the checker rejected: "
                            + "; ".join(f"[{e['code']}] {e['message']}" for e in errors))
            continue
        layouts.append(layout)
        extras.append({
            "archetype": variant.get("archetype"),
            "penalties": variant.get("penalties", {}),
            "coverage_percent": variant.get("coverage_percent", _coverage(variant)),
        })
    # P3's schema is the contract; extra fields are added after it has passed.
    output = FloorPlanOutput(layouts=layouts).model_dump()
    return {
        "status": "valid" if layouts else "invalid",
        "layouts": [{**layout, **extra} for layout, extra in zip(output["layouts"], extras)],
        "messages": messages,
    }


def _coverage(variant: Dict[str, Any]) -> float:
    used = sum(r["area"] for r in variant["rooms"].values())
    used += sum(s["area"] for s in variant.get("hallway_segments", []))
    return round(100 * used / (variant["buildable_width"] * variant["buildable_depth"]), 2)


# --- why nothing was found -------------------------------------------------------------------------

def probe(args: Dict[str, Any], time_limit: float = PROBE_SECONDS) -> Dict[str, Any]:
    """Does any layout exist? Only hard rules count, and the first solution is enough."""
    hard_only = {name: pref for name, pref in (args.get("preferences") or {}).items()
                 if pref.get("zone_mode", "try") == "must"}
    return solve_with_preferences(**{
        **args,
        "preferences": hard_only,
        "preferred_adjacencies": None,
        "gap_weight": 0,
        "hallway_weight": 0,
        "previous_layout": None,
        "relative_gap_limit": 1.0,
        "time_limit_seconds": time_limit,
    })


def find_must_conflict(args: Dict[str, Any]) -> List[str]:
    """The smallest set of 'must' rooms that cannot hold together, or [] if zones are not the cause."""
    prefs = args.get("preferences") or {}
    musts = [name for name, pref in prefs.items() if pref.get("zone_mode", "try") == "must"]
    if not musts:
        return []

    def with_musts(names):
        keep = {name: pref for name, pref in prefs.items() if name in names}
        return {**args, "preferences": keep}

    if probe(with_musts([]))["status"] != "success":
        return []  # impossible even with no zones at all

    needed = list(musts)
    for name in musts:  # drop each room that is not part of the conflict
        trial = [n for n in needed if n != name]
        if probe(with_musts(trial))["status"] == "infeasible":
            needed = trial
    return needed


def explain_failure(inp, args, attempts) -> Dict[str, Any]:
    """Result when no layout was found: conflict, infeasible or timeout, with the reason."""
    for attempt in attempts:
        rooms = find_must_conflict(attempt)
        if rooms:
            zones = ", ".join(f"{name} in {args['preferences'][name]['zone']}" for name in rooms)
            return {
                "status": "conflict",
                "layouts": [],
                "conflict_rooms": rooms,
                "messages": [f"These 'must' directions cannot hold with the other hard rules: {zones}. "
                             "Change the zone or mark it 'try'."],
            }
    results = [probe(attempt, PROBE_SECONDS) for attempt in attempts]
    if any(r["status"] == "timeout" for r in results):
        return {"status": "timeout", "layouts": [], "messages": [results[0]["message"]]}
    searched = f" Searched hallways of up to {args['max_hallway_segments']} segments, and no hallway."
    return {"status": "infeasible", "layouts": [], "messages": [results[0]["message"] + searched]}


# --- public calls ----------------------------------------------------------------------------------

def solve_request(
    inp: Dict[str, Any],
    count: int = MAX_LAYOUT_ALTERNATIVES,
    time_limit_seconds: float = SOLVER_TIME_LIMIT_SECONDS,
    max_hallway_segments: int = MAX_HALLWAY_SEGMENTS,
    locked_rooms: Optional[Dict[str, Dict[str, int]]] = None,
    previous_layout: Optional[Dict[str, Dict[str, int]]] = None,
) -> Dict[str, Any]:
    """Run the engine on one input dict. See the module docstring for the result."""
    bad_input = check_input(inp)
    if bad_input:
        return {"status": "invalid", "layouts": [], "messages": [p["message"] for p in bad_input]}
    if not any(room["type"] == "living" for room in inp["rooms"]):
        return {"status": "invalid", "layouts": [],
                "messages": ["At least one living room is required: it is the entrance room."]}

    table = room_size_table(inp)
    args = build_preference_arguments(inp, table, preferred_sizes(inp))
    args.update(
        time_limit_seconds=time_limit_seconds,
        max_hallway_segments=max_hallway_segments,
        locked_rooms=locked_rooms,
        previous_layout=previous_layout,
    )

    too_much = check_area(args)
    if too_much:
        return {"status": "infeasible", "layouts": [], "messages": [too_much]}

    # An edit keeps its one plan; a fresh request tries the archetypes.
    archetypes = () if previous_layout else ARCHETYPES
    variants = generate_variants(count=count, archetypes=archetypes, **args)
    attempts = [args]
    if not variants:
        found = probe(args, time_limit_seconds)
        if found["status"] == "success":
            # A layout exists but the scored search ran out of time: return it rather than nothing.
            variants = [{**found, "archetype": None}]
        elif found["status"] == "infeasible":
            # Team decision (connection_rules.md, item 8): a small plot may have no hallway.
            no_hallway = build_no_hallway_arguments(args, inp)
            attempts.append(no_hallway)
            variants = generate_variants(count=count, archetypes=(), **no_hallway)
    if not variants:
        return explain_failure(inp, args, attempts)

    return build_output(inp, variants, table)


def edit_layout(
    inp: Dict[str, Any],
    layout: Dict[str, Any],
    edits: Dict[str, Dict[str, int]],
    lock: Optional[List[str]] = None,
    time_limit_seconds: float = SOLVER_TIME_LIMIT_SECONDS,
    max_hallway_segments: int = MAX_HALLWAY_SEGMENTS,
) -> Dict[str, Any]:
    """Edit Rules: turn a change into pins and solve the whole model again, moving rooms as little as possible.

    edits is {room: {"width": 14, "height": 12}}. lock names rooms that must stay exactly where they are.
    The result has one layout and the updated "input", or the reason and the "nearest" value that works.
    """
    names = {room["name"] for room in inp["rooms"]}
    unknown = sorted((set(edits) | set(lock or [])) - names)
    if unknown:
        return {"status": "invalid", "layouts": [], "messages": [f"Unknown room: {unknown[0]}"]}

    pins = {pin["room"]: dict(pin) for pin in inp.get("pins", [])}
    # A pin with "locked": true stays where it is, the same as a room named in lock.
    lock = set(lock or []) | {name for name, pin in pins.items() if pin.get("locked")}
    unlocked = sorted(lock & set(edits))  # an edited room cannot also stay frozen
    kept = sorted(lock - set(edits))
    for room, values in edits.items():
        pin = pins.setdefault(room, {"room": room})
        pin.update(values)
        pin.pop("locked", None)
    for name in kept:  # written back so the lock carries over to the next edit
        pins.setdefault(name, {"room": name})["locked"] = True
    new_inp = {**inp, "pins": list(pins.values())}

    placed = {r["name"]: r for r in layout["rooms"]}
    previous = {name: {"x": r["x"], "y": r["y"]} for name, r in placed.items()}
    locked = {name: {"x": placed[name]["x"], "y": placed[name]["y"],
                     "width": placed[name]["w"], "height": placed[name]["h"]} for name in kept}
    messages = [f"{name} was edited, so it was unlocked." for name in unlocked]

    table = room_size_table(new_inp)
    result = {}
    in_limits = all(value in _allowed_values(new_inp, table, room, side)
                    for room, values in edits.items() for side, value in values.items())
    if in_limits:
        result = solve_request(new_inp, count=1, time_limit_seconds=time_limit_seconds,
                               max_hallway_segments=max_hallway_segments,
                               locked_rooms=locked or None, previous_layout=previous)
        if result["status"] == "valid":
            return {**result, "input": new_inp, "messages": messages + result["messages"]}
        if result["status"] == "timeout":
            return {**result, "input": new_inp, "messages": messages + result["messages"]}

    nearest = _nearest_working_values(inp, edits, table, locked, previous, max_hallway_segments)
    reasons = [f"{room} {side} {value} ft"
               for room, values in edits.items() for side, value in values.items()]
    text = f"This edit cannot be built: {', '.join(reasons)}."
    for room, values in nearest.items():
        for side, value in values.items():
            text += f" Nearest {room} {side} that works: {value} ft."
    if not nearest:
        text += " No nearby value works either."
    blocking = []
    if in_limits and locked:
        # In a tightly packed plan a locked room can be what blocks the new size. One more solve, only
        # on failure, tells the user whether unpinning would let the size they asked for fit.
        free = solve_request(new_inp, count=1, time_limit_seconds=time_limit_seconds,
                             max_hallway_segments=max_hallway_segments, previous_layout=previous)
        if free["status"] == "valid":
            blocking = sorted(locked)
            text += f" It fits if {', '.join(blocking)} may move: unpin {'it' if len(blocking) == 1 else 'them'}."
    return {"status": "infeasible", "layouts": [], "nearest": nearest, "blocking_locks": blocking,
            "messages": messages + [text]}


def _allowed_values(inp, table, room_name, side):
    """Sizes the size table allows on one side of a room, either way round for a turnable room."""
    room = next(r for r in inp["rooms"] if r["name"] == room_name)
    low, high = table[room["type"]]
    low, high = room.get("min", low), room.get("max", high)
    index = 0 if side == "width" else 1
    allowed = set(range(low[index], high[index] + 1))
    if list(low) != list(low)[::-1] or list(high) != list(high)[::-1]:
        allowed |= set(range(low[1 - index], high[1 - index] + 1))
    return allowed


def _nearest_working_values(inp, edits, table, locked, previous, max_hallway_segments):
    """For each edited value, the closest value that gives a layout when only that value changes."""
    nearest: Dict[str, Dict[str, int]] = {}
    base_pins = {pin["room"]: dict(pin) for pin in inp.get("pins", [])}
    for room, values in edits.items():
        for side, wanted in values.items():
            candidates = sorted(_allowed_values(inp, table, room, side), key=lambda v: (abs(v - wanted), v))
            for value in candidates:
                if value == wanted:
                    continue
                pins = {**base_pins, room: {**base_pins.get(room, {"room": room}), side: value}}
                trial = {**inp, "pins": list(pins.values())}
                args = build_preference_arguments(trial, room_size_table(trial), preferred_sizes(trial))
                args.update(max_hallway_segments=max_hallway_segments, locked_rooms=locked or None)
                if probe(args)["status"] == "success":
                    nearest.setdefault(room, {})[side] = value
                    break
    return nearest
