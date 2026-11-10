"""Preferences and Intelligence module for the 2D Floor Planning Engine (P2).

P1's solve_layout owns the model: rooms, hallway segments and the hard geometry rules. This module
adds its rules to that same model through solve_layout's model_extension hook.

Owns:
- Direction zones (3x3 grid: NW, N, NE, W, Mid, E, SW, S, SE), turned by the input's `north` field
- Hard zone constraints (H7: 'must' direction)
- Soft zone preferences (S2: 'try' direction)
- Required adjacency with minimum shared wall length for doors (H6)
- Soft preferences & scoring (S1: preferred sizes, S3: hallway waste, S4: adjacency quality, S5: entrance side, S6: minimal change)
- Variant generation (3 distinct layouts, by archetype)
- Edit and re-solve with pinned / locked rooms
"""

from typing import Dict, List, Optional, Tuple, Any
from ortools.sat.python import cp_model

from floorplan.connections import add_adjacency
from floorplan.geometry import (
    DEFAULT_ROOM_SPECS,
    ENTRANCE_EDGE,
    HALLWAY_MAX_SHORT_SIDE,
    solve_layout,
)


# 3x3 Zone Grid relative cell bounds in range [0, 3] along X and Y axes.
# Coordinates assume North = Top (+y), South = Bottom (0), West = Left (0), East = Right (+x).
ZONE_MAP: Dict[str, Tuple[Tuple[int, int], Tuple[int, int]]] = {
    # zone_name: ((x_min_fraction_numerator, x_max_fraction_numerator), (y_min_fraction_numerator, y_max_fraction_numerator)) / 3
    "NW":  ((0, 1), (2, 3)),
    "N":   ((1, 2), (2, 3)),
    "NE":  ((2, 3), (2, 3)),
    "W":   ((0, 1), (1, 2)),
    "Mid": ((1, 2), (1, 2)),
    "E":   ((2, 3), (1, 2)),
    "SW":  ((0, 1), (0, 1)),
    "S":   ((1, 2), (0, 1)),
    "SE":  ((2, 3), (0, 1)),
}

DOOR_MIN = 3  # ft, shortest shared wall that can hold a door (connection_rules.md)

# Plan shapes tried for variants (Variant Rules in the MVP plan).
ARCHETYPES = ("central_hallway", "side_corridor", "living_center")

# The ZONE_MAP / entrance letter for each drawing edge (ZONE_MAP is written with north up).
EDGE_SIDE = {"top": "N", "bottom": "S", "left": "W", "right": "E"}


def to_drawing_side(side: str, north: str = "up") -> str:
    """Turn a real-world side (N, S, E, W) into the side of the drawing it lands on."""
    return EDGE_SIDE[ENTRANCE_EDGE[north][side.upper()]]


def to_drawing_zone(zone: str, north: str = "up") -> str:
    """Turn a real-world zone such as 'NW' into the ZONE_MAP cell it lands on in the drawing."""
    if zone == "Mid" or north == "up":
        return zone
    sides = [to_drawing_side(s, north) for s in zone]
    return "".join(s for s in sides if s in "NS") + "".join(s for s in sides if s in "EW")


def calculate_zone_bounds(
    buildable_width: int,
    buildable_depth: int,
    zone_name: str
) -> Dict[str, int]:
    """Calculate the integer bounds of a 3x3 zone cell within the buildable footprint.

    Returns a dict with 'x_min', 'x_max', 'y_min', 'y_max'.
    """
    if zone_name not in ZONE_MAP:
        raise ValueError(f"Unknown zone '{zone_name}'. Must be one of: {list(ZONE_MAP.keys())}")

    (x_num_min, x_num_max), (y_num_min, y_num_max) = ZONE_MAP[zone_name]

    # Partition buildable width and depth into 3 parts
    x_min = (x_num_min * buildable_width) // 3
    x_max = (x_num_max * buildable_width) // 3 if x_num_max < 3 else buildable_width
    y_min = (y_num_min * buildable_depth) // 3
    y_max = (y_num_max * buildable_depth) // 3 if y_num_max < 3 else buildable_depth

    return {
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
    }


def add_must_zone_constraint(
    model: cp_model.CpModel,
    x_var: cp_model.IntVar,
    y_var: cp_model.IntVar,
    w_var: cp_model.IntVar,
    h_var: cp_model.IntVar,
    buildable_width: int,
    buildable_depth: int,
    zone_name: str,
) -> None:
    """Rule H7: Enforce that the room's geometric center falls inside the specified zone.

    The zone is an exact third of the buildable width and depth. Whole-number arithmetic, scaled by 6:
        lo * W / 3 <= center_x = (2 * x + width) / 2 <= hi * W / 3
        <=>  2 * lo * W <= 3 * (2 * x + width) <= 2 * hi * W
    (Rounding the thirds to whole feet let a centre at y = 10 count as the middle row of a 31 ft plot,
    whose true boundary is 10.33 ft.)
    """
    if zone_name not in ZONE_MAP:
        raise ValueError(f"Unknown zone '{zone_name}'. Must be one of: {list(ZONE_MAP.keys())}")
    (x_lo, x_hi), (y_lo, y_hi) = ZONE_MAP[zone_name]

    model.add(3 * (2 * x_var + w_var) >= 2 * x_lo * buildable_width)
    model.add(3 * (2 * x_var + w_var) <= 2 * x_hi * buildable_width)
    model.add(3 * (2 * y_var + h_var) >= 2 * y_lo * buildable_depth)
    model.add(3 * (2 * y_var + h_var) <= 2 * y_hi * buildable_depth)


def add_try_zone_penalty(
    model: cp_model.CpModel,
    x_var: cp_model.IntVar,
    y_var: cp_model.IntVar,
    w_var: cp_model.IntVar,
    h_var: cp_model.IntVar,
    buildable_width: int,
    buildable_depth: int,
    zone_name: str,
    weight: int = 10,
    prefix: str = "",
) -> cp_model.IntVar:
    """Rule S2: Penalize distance of room center from the target zone cell center."""
    bounds = calculate_zone_bounds(buildable_width, buildable_depth, zone_name)

    # Target zone center scaled by 2
    target_cx_x2 = bounds["x_min"] + bounds["x_max"]
    target_cy_x2 = bounds["y_min"] + bounds["y_max"]

    # Difference in x (scaled by 2)
    diff_x = model.new_int_var(-2 * buildable_width, 2 * buildable_width, f"{prefix}_diff_x")
    model.add(diff_x == (2 * x_var + w_var) - target_cx_x2)

    abs_diff_x = model.new_int_var(0, 2 * buildable_width, f"{prefix}_abs_diff_x")
    model.add_abs_equality(abs_diff_x, diff_x)

    # Difference in y (scaled by 2)
    diff_y = model.new_int_var(-2 * buildable_depth, 2 * buildable_depth, f"{prefix}_diff_y")
    model.add(diff_y == (2 * y_var + h_var) - target_cy_x2)

    abs_diff_y = model.new_int_var(0, 2 * buildable_depth, f"{prefix}_abs_diff_y")
    model.add_abs_equality(abs_diff_y, diff_y)

    total_dist = model.new_int_var(0, 2 * (buildable_width + buildable_depth), f"{prefix}_zone_dist")
    model.add(total_dist == abs_diff_x + abs_diff_y)

    if weight == 1:
        return total_dist

    penalty = model.new_int_var(0, 2 * (buildable_width + buildable_depth) * weight, f"{prefix}_zone_pen")
    model.add(penalty == total_dist * weight)
    return penalty


def add_required_adjacency(
    model: cp_model.CpModel,
    room_a: Dict[str, cp_model.IntVar],
    room_b: Dict[str, cp_model.IntVar],
    buildable_width: int,
    buildable_depth: int,
    min_door_width: int = DOOR_MIN,
    prefix: str = "adj",
) -> cp_model.IntVar:
    """Rule H6: Rooms that must connect share a wall at least min_door_width long.

    Returns a boolean variable z that is True iff room_a and room_b share a wall of length >= min_door_width.
    """
    xa, ya, wa, ha = room_a["x"], room_a["y"], room_a["width"], room_a["height"]
    xb, yb, wb, hb = room_b["x"], room_b["y"], room_b["width"], room_b["height"]

    # Compute end positions
    xae = xa + wa
    yae = ya + ha
    xbe = xb + wb
    ybe = yb + hb

    d = min_door_width
    opts = []
    p_and_q = [
        (xa, ya, xae, yae, xb, yb, xbe, ybe, "a_then_b"),
        (xb, yb, xbe, ybe, xa, ya, xae, yae, "b_then_a"),
    ]

    for px, py, pxe, pye, qx, qy, qxe, qye, side_label in p_and_q:
        # p directly west of q. Shared wall = min(pye, qye) - max(py, qy) >= d,
        # which needs all four end-minus-start pairs to be >= d.
        west = model.new_bool_var(f"{prefix}_{side_label}_west")
        model.add(pxe == qx).only_enforce_if(west)
        model.add(py + d <= qye).only_enforce_if(west)
        model.add(qy + d <= pye).only_enforce_if(west)
        model.add(py + d <= pye).only_enforce_if(west)
        model.add(qy + d <= qye).only_enforce_if(west)

        # p directly south of q (y grows north). Shared wall = min(pxe, qxe) - max(px, qx) >= d.
        south = model.new_bool_var(f"{prefix}_{side_label}_south")
        model.add(pye == qy).only_enforce_if(south)
        model.add(px + d <= qxe).only_enforce_if(south)
        model.add(qx + d <= pxe).only_enforce_if(south)
        model.add(px + d <= pxe).only_enforce_if(south)
        model.add(qx + d <= qxe).only_enforce_if(south)

        opts.extend([west, south])

    z = model.new_bool_var(f"{prefix}_connected")
    model.add_bool_or(opts).only_enforce_if(z)
    model.add(z == 1)  # Required hard adjacency
    return z


def add_preferred_size_penalty(
    model: cp_model.CpModel,
    w_var: cp_model.IntVar,
    h_var: cp_model.IntVar,
    pref_w: int,
    pref_h: int,
    max_w: int,
    max_h: int,
    weight: int = 1,
    prefix: str = "size",
) -> cp_model.IntVar:
    """Rule S1: Penalize distance of room width and height from preferred values."""
    diff_w = model.new_int_var(-max_w, max_w, f"{prefix}_diff_w")
    model.add(diff_w == w_var - pref_w)
    abs_diff_w = model.new_int_var(0, max_w, f"{prefix}_abs_diff_w")
    model.add_abs_equality(abs_diff_w, diff_w)

    diff_h = model.new_int_var(-max_h, max_h, f"{prefix}_diff_h")
    model.add(diff_h == h_var - pref_h)
    abs_diff_h = model.new_int_var(0, max_h, f"{prefix}_abs_diff_h")
    model.add_abs_equality(abs_diff_h, diff_h)

    total_diff = model.new_int_var(0, (max_w + max_h) * weight, f"{prefix}_pen")
    model.add(total_diff == (abs_diff_w + abs_diff_h) * weight)
    return total_diff


def add_entrance_side_penalty(
    model: cp_model.CpModel,
    x_var: cp_model.IntVar,
    y_var: cp_model.IntVar,
    w_var: cp_model.IntVar,
    h_var: cp_model.IntVar,
    buildable_width: int,
    buildable_depth: int,
    entrance_side: str,  # 'N', 'S', 'E', 'W'
    weight: int = 5,
    prefix: str = "entrance",
) -> cp_model.IntVar:
    """Rule S5: Penalize living/entrance room center away from the chosen entrance side.

    entrance_side is a side of the DRAWING (north up). Use to_drawing_side() for a rotated plot.
    """
    entrance_side = entrance_side.upper()
    pen = model.new_int_var(0, 2 * max(buildable_width, buildable_depth) * weight, f"{prefix}_pen")

    if entrance_side == "S":
        # Distance of room bottom from y=0
        model.add(pen == y_var * weight)
    elif entrance_side == "N":
        # Distance of room top from y=buildable_depth
        model.add(pen == (buildable_depth - (y_var + h_var)) * weight)
    elif entrance_side == "W":
        # Distance of room left from x=0
        model.add(pen == x_var * weight)
    elif entrance_side == "E":
        # Distance of room right from x=buildable_width
        model.add(pen == (buildable_width - (x_var + w_var)) * weight)
    else:
        raise ValueError(f"Unknown entrance side '{entrance_side}'. Must be N, S, E, or W.")

    return pen


def add_entrance_wall_constraint(
    model: cp_model.CpModel,
    x_var: cp_model.IntVar,
    y_var: cp_model.IntVar,
    w_var: cp_model.IntVar,
    h_var: cp_model.IntVar,
    buildable_width: int,
    buildable_depth: int,
    entrance_side: str,  # side of the DRAWING: 'N', 'S', 'E', 'W'
) -> None:
    """Rule E1 (hard): the entrance room touches the buildable edge on the entrance side."""
    entrance_side = entrance_side.upper()
    if entrance_side == "S":
        model.add(y_var == 0)
    elif entrance_side == "N":
        model.add(y_var + h_var == buildable_depth)
    elif entrance_side == "W":
        model.add(x_var == 0)
    elif entrance_side == "E":
        model.add(x_var + w_var == buildable_width)
    else:
        raise ValueError(f"Unknown entrance side '{entrance_side}'. Must be N, S, E, or W.")


def add_minimal_change_penalty(
    model: cp_model.CpModel,
    x_var: cp_model.IntVar,
    y_var: cp_model.IntVar,
    prev_x: int,
    prev_y: int,
    buildable_width: int,
    buildable_depth: int,
    weight: int = 10,
    prefix: str = "edit",
) -> cp_model.IntVar:
    """Rule S6: Minimal change penalty on edit. Penalize room movement from previous position."""
    diff_x = model.new_int_var(-buildable_width, buildable_width, f"{prefix}_diff_x")
    model.add(diff_x == x_var - prev_x)
    abs_diff_x = model.new_int_var(0, buildable_width, f"{prefix}_abs_diff_x")
    model.add_abs_equality(abs_diff_x, diff_x)

    diff_y = model.new_int_var(-buildable_depth, buildable_depth, f"{prefix}_diff_y")
    model.add(diff_y == y_var - prev_y)
    abs_diff_y = model.new_int_var(0, buildable_depth, f"{prefix}_abs_diff_y")
    model.add_abs_equality(abs_diff_y, diff_y)

    total_dist = model.new_int_var(0, (buildable_width + buildable_depth) * weight, f"{prefix}_pen")
    model.add(total_dist == (abs_diff_x + abs_diff_y) * weight)
    return total_dist


def add_preferred_adjacency_penalty(
    model: cp_model.CpModel,
    room_a: Dict[str, Any],
    room_b: Dict[str, Any],
    buildable_width: int,
    buildable_depth: int,
    weight: int = 2,
    prefix: str = "near",
) -> Any:
    """Rule S4: Penalize the walking gap between rooms that should be close. Touching costs nothing."""
    xa, ya, wa, ha = room_a["x"], room_a["y"], room_a["width"], room_a["height"]
    xb, yb, wb, hb = room_b["x"], room_b["y"], room_b["width"], room_b["height"]

    gap_x = model.new_int_var(0, buildable_width, f"{prefix}_gap_x")
    model.add_max_equality(gap_x, [0, xa - (xb + wb), xb - (xa + wa)])
    gap_y = model.new_int_var(0, buildable_depth, f"{prefix}_gap_y")
    model.add_max_equality(gap_y, [0, ya - (yb + hb), yb - (ya + ha)])
    return (gap_x + gap_y) * weight


def add_connect_to_any(
    model: cp_model.CpModel,
    room: Dict[str, Any],
    hallway_slots: List[Dict[str, Any]],
    other_rooms: List[Dict[str, Any]],
    buildable_width: int,
    buildable_depth: int,
    prefix: str = "reach",
) -> None:
    """Rule F5 for rooms with no required partner (dining, utility, store): touch any hallway or listed room."""
    choices = []
    for index, slot in enumerate(hallway_slots):
        choice = model.new_bool_var(f"{prefix}_hall_{index}")
        add_adjacency(model, room, slot["vars"], DOOR_MIN, buildable_width, buildable_depth,
                      f"{prefix}_hall_{index}_wall", enforce=choice)
        model.add_implication(choice, slot["active"])
        choices.append(choice)
    for index, other in enumerate(other_rooms):
        choice = model.new_bool_var(f"{prefix}_room_{index}")
        add_adjacency(model, room, other, DOOR_MIN, buildable_width, buildable_depth,
                      f"{prefix}_room_{index}_wall", enforce=choice)
        choices.append(choice)
    model.add_bool_or(choices)


def add_archetype_constraints(
    model: cp_model.CpModel,
    archetype: str,
    entrance_room: Optional[Dict[str, Any]],
    entrance_side: Optional[str],
    hallway_slots: List[Dict[str, Any]],
    buildable_width: int,
    buildable_depth: int,
) -> None:
    """Variant Rules: shape the plan as a central hallway, a side corridor or a centered living room."""
    W, L = buildable_width, buildable_depth

    if archetype == "living_center":
        if entrance_room is None or entrance_side is None:
            return
        # Center of the living room in the middle third of the entrance wall (exact, no rounding).
        if entrance_side in ("S", "N"):
            center2, span = 2 * entrance_room["x"] + entrance_room["width"], W
        else:
            center2, span = 2 * entrance_room["y"] + entrance_room["height"], L
        model.add(3 * center2 >= 2 * span)
        model.add(3 * center2 <= 4 * span)
        return

    if archetype not in ARCHETYPES:
        raise ValueError(f"Unknown archetype '{archetype}'. Must be one of: {list(ARCHETYPES)}.")
    if not hallway_slots:
        return
    hall = hallway_slots[0]["vars"]
    x, y, w, h = hall["x"], hall["y"], hall["w"], hall["h"]
    vertical = model.new_bool_var(f"{archetype}_vertical")
    model.add(w <= HALLWAY_MAX_SHORT_SIDE).only_enforce_if(vertical)
    model.add(h <= HALLWAY_MAX_SHORT_SIDE).only_enforce_if(~vertical)

    if archetype == "central_hallway":
        # A full-length spine with room on both sides of it.
        model.add(h == L).only_enforce_if(vertical)
        model.add(x >= 1).only_enforce_if(vertical)
        model.add(x + w <= W - 1).only_enforce_if(vertical)
        model.add(w == W).only_enforce_if(~vertical)
        model.add(y >= 1).only_enforce_if(~vertical)
        model.add(y + h <= L - 1).only_enforce_if(~vertical)
    else:  # side_corridor: at least two thirds of the length, against an outer wall
        at_left = model.new_bool_var("side_at_left")
        at_right = model.new_bool_var("side_at_right")
        at_bottom = model.new_bool_var("side_at_bottom")
        at_top = model.new_bool_var("side_at_top")
        model.add(x == 0).only_enforce_if(at_left)
        model.add(x + w == W).only_enforce_if(at_right)
        model.add(y == 0).only_enforce_if(at_bottom)
        model.add(y + h == L).only_enforce_if(at_top)
        model.add(3 * h >= 2 * L).only_enforce_if(vertical)
        model.add(3 * w >= 2 * W).only_enforce_if(~vertical)
        model.add_bool_or([~vertical, at_left, at_right])
        model.add_bool_or([vertical, at_bottom, at_top])


def zone_contains(room: Dict[str, int], zone_name: str, buildable_width: int, buildable_depth: int) -> bool:
    """Whether a solved room's center lies in a zone cell of the drawing (same test as rule H7)."""
    (x_lo, x_hi), (y_lo, y_hi) = ZONE_MAP[zone_name]
    cx6 = 3 * (2 * room["x"] + room["width"])
    cy6 = 3 * (2 * room["y"] + room["height"])
    return (2 * x_lo * buildable_width <= cx6 <= 2 * x_hi * buildable_width
            and 2 * y_lo * buildable_depth <= cy6 <= 2 * y_hi * buildable_depth)


def solve_with_preferences(
    plot_width: int = 30,
    plot_height: int = 40,
    room_specs: Optional[Dict[str, Dict[str, Any]]] = None,
    setbacks: Optional[Dict[str, int]] = None,
    preferences: Optional[Dict[str, Dict[str, Any]]] = None,
    required_adjacencies: Optional[List[Tuple[str, str]]] = None,
    entrance: Optional[str] = "S",
    time_limit_seconds: float = 10.0,
    locked_rooms: Optional[Dict[str, Dict[str, int]]] = None,
    pinned_dimensions: Optional[Dict[str, Dict[str, int]]] = None,
    previous_layout: Optional[Dict[str, Dict[str, int]]] = None,
    exclude_zone_assignments: Optional[List[Dict[str, str]]] = None,
    north: str = "up",
    include_hallway: bool = False,
    layout_input: Optional[Dict[str, Any]] = None,
    max_hallway_segments: int = 3,
    fill_plot: bool = False,
    gap_weight: int = 0,
    hallway_weight: int = 1,
    preferred_adjacencies: Optional[List[Tuple[str, str]]] = None,
    must_connect: Optional[List[str]] = None,
    entrance_wall: bool = False,
    entrance_room: Optional[str] = None,
    archetype: Optional[str] = None,
    relative_gap_limit: float = 0.05,
) -> Dict[str, Any]:
    """Solve floor plan layout: P1's geometry and hallway model plus the P2 preference rules.

    P1's solve_layout builds the rooms, hallway segments and hard geometry. Everything here is added
    to that same model through its model_extension hook, so there is only one model.

    Args:
        plot_width: Total plot width in feet.
        plot_height: Total plot depth in feet.
        room_specs: Dictionary of room specifications (min/max width and height, optional pref_width/pref_height,
            optional rotatable=True).
        setbacks: Front, back, left, right setback distances.
        preferences: Optional room zone preferences e.g. {'kitchen': {'zone': 'SE', 'zone_mode': 'must'}}.
            Zones are real-world directions and are turned by `north`.
        required_adjacencies: List of (room_a, room_b) pairs that must share a door-width wall (H6).
            Hallway connections come from layout_input through P1's required_pairs.
        entrance: Chosen real-world entrance side ('N', 'S', 'E', 'W').
        time_limit_seconds: Maximum solver search time in seconds.
        locked_rooms: Dict of room_name -> {'x': int, 'y': int, 'width': int, 'height': int}.
        pinned_dimensions: Dict of room_name -> {'width': int, 'height': int, etc.}.
        previous_layout: Dict of room_name -> {'x': int, 'y': int} for S6 minimal change on edit.
        exclude_zone_assignments: List of prior zone mappings to enforce variant diversity.
        north: Where north points in the drawing ('up', 'down', 'left', 'right').
        include_hallway: Add P1's hallway segments and required connections. Needs layout_input.
        layout_input: The input dict P1 reads room types, attached_to, entrance and north from.
        max_hallway_segments: Hallway candidate slots passed to P1.
        fill_plot: Rooms and hallway must cover the buildable area exactly (H4 as a hard rule).
        gap_weight: Points per unused sq ft. Pulls the plan towards full coverage without requiring it.
        hallway_weight: Points per sq ft of hallway (S3).
        preferred_adjacencies: Pairs of rooms that should be close (S4).
        must_connect: Rooms that must touch any hallway segment or the entrance room, so they can be reached.
        entrance_wall: The entrance room must touch the entrance edge (E1). P1 adds this itself with a hallway.
        entrance_room: Name of the entrance room. Defaults to 'living', else the first room.
        archetype: One of ARCHETYPES, or None for no particular plan shape.
        relative_gap_limit: How close to the best possible score the solver must get before it stops.
    """
    if room_specs is None:
        room_specs = DEFAULT_ROOM_SPECS

    if setbacks is None:
        setbacks = {"left": 0, "right": 0, "front": 0, "back": 0}

    if north not in ENTRANCE_EDGE:
        raise ValueError(f"Unknown north '{north}'. Must be one of: {list(ENTRANCE_EDGE)}.")

    # Unknown names raise here rather than silently dropping a rule.
    for kind, pairs in (("Required", required_adjacencies), ("Preferred", preferred_adjacencies)):
        for ra, rb in pairs or []:
            missing = [n for n in (ra, rb) if n not in room_specs]
            if missing:
                raise ValueError(f"{kind} adjacency ({ra}, {rb}) names unknown room '{missing[0]}'.")
    if entrance_room is not None and entrance_room not in room_specs:
        raise ValueError(f"Entrance room '{entrance_room}' is not in room_specs.")

    # Pins on fixed-orientation rooms narrow the spec; a turnable room is pinned inside the model below.
    specs = {}
    for name, spec in room_specs.items():
        spec = dict(spec)
        pin = (pinned_dimensions or {}).get(name, {})
        if pin and not spec.get("rotatable"):
            if "width" in pin:
                spec["min_width"] = spec["max_width"] = pin["width"]
            if "height" in pin:
                spec["min_height"] = spec["max_height"] = pin["height"]
        specs[name] = spec

    if entrance_room is None:
        entrance_room = "living" if "living" in specs else next(iter(specs), None)

    def extension(model, ctx):
        W, L = ctx["W"], ctx["L"]
        x_vars, y_vars = ctx["x"], ctx["y"]
        width_vars, height_vars = ctx["w"], ctx["h"]

        def vars_of(name):
            return {"x": x_vars[name], "y": y_vars[name], "w": width_vars[name], "h": height_vars[name],
                    "width": width_vars[name], "height": height_vars[name]}

        for name, spec in specs.items():
            pin = (pinned_dimensions or {}).get(name, {})
            if pin and spec.get("rotatable"):
                if "width" in pin:
                    model.add(width_vars[name] == pin["width"])
                if "height" in pin:
                    model.add(height_vars[name] == pin["height"])

            # Locked room position & dimension (Edit mode)
            if locked_rooms and name in locked_rooms:
                lr = locked_rooms[name]
                model.add(x_vars[name] == lr["x"])
                model.add(y_vars[name] == lr["y"])
                model.add(width_vars[name] == lr["width"])
                model.add(height_vars[name] == lr["height"])

        # Hard Adjacency Rules (H6)
        for idx, (ra, rb) in enumerate(required_adjacencies or []):
            add_required_adjacency(
                model, vars_of(ra), vars_of(rb), W, L,
                min_door_width=DOOR_MIN, prefix=f"req_adj_{idx}_{ra}_{rb}",
            )

        # Rooms that only need to be reachable (F5)
        for idx, name in enumerate(must_connect or []):
            others = [vars_of(entrance_room)] if entrance_room and entrance_room != name else []
            add_connect_to_any(model, vars_of(name), ctx["hallway_slots"], others, W, L, f"reach_{idx}_{name}")

        penalties: Dict[str, Any] = {}

        def charge(rule, expr):
            penalties[rule] = penalties.get(rule, 0) + expr

        # Zone Preferences (H7 must, S2 try)
        for name, pref in (preferences or {}).items():
            if name not in specs or not pref.get("zone"):
                continue
            zone = to_drawing_zone(pref["zone"], north)
            mode = pref.get("zone_mode", "try")
            if mode == "must":
                add_must_zone_constraint(model, x_vars[name], y_vars[name], width_vars[name], height_vars[name],
                                         W, L, zone)
            elif mode == "try":
                charge("S2_try_zones", add_try_zone_penalty(
                    model, x_vars[name], y_vars[name], width_vars[name], height_vars[name], W, L, zone,
                    weight=pref.get("weight", 10), prefix=f"pref_{name}",
                ))

        # Preferred Sizes (S1)
        for name, spec in specs.items():
            pref_w = spec.get("pref_width")
            pref_h = spec.get("pref_height")
            if pref_w is not None and pref_h is not None:
                longest = max(spec["max_width"], spec["max_height"], pref_w, pref_h)
                charge("S1_preferred_sizes", add_preferred_size_penalty(
                    model, width_vars[name], height_vars[name], pref_w, pref_h, longest, longest,
                    weight=spec.get("size_weight", 2), prefix=f"size_{name}",
                ))

        # Hallway Waste (S3)
        if ctx["hallway_slots"] and hallway_weight:
            charge("S3_hallway_area", sum(slot["area"] for slot in ctx["hallway_slots"]) * hallway_weight)

        # Adjacency Quality (S4)
        for idx, (ra, rb) in enumerate(preferred_adjacencies or []):
            charge("S4_adjacency_quality", add_preferred_adjacency_penalty(
                model, vars_of(ra), vars_of(rb), W, L, prefix=f"near_{idx}_{ra}_{rb}"))

        # Entrance Proximity (S5) and entrance wall (E1)
        side = to_drawing_side(entrance, north) if entrance else None
        if side and entrance_room:
            room = vars_of(entrance_room)
            charge("S5_entrance_side", add_entrance_side_penalty(
                model, room["x"], room["y"], room["w"], room["h"], W, L,
                entrance_side=side, weight=5, prefix="ent_pen",
            ))
            if entrance_wall:
                add_entrance_wall_constraint(model, room["x"], room["y"], room["w"], room["h"], W, L, side)

        # Minimal Change on Edit (S6)
        for name, prev_pos in (previous_layout or {}).items():
            if name in specs and (not locked_rooms or name not in locked_rooms):
                charge("S6_minimal_change", add_minimal_change_penalty(
                    model, x_vars[name], y_vars[name], prev_pos["x"], prev_pos["y"], W, L,
                    weight=15, prefix=f"edit_{name}",
                ))

        # Unused floor area: full coverage is what H4 asks for, so it outweighs the other penalties
        if gap_weight:
            charge("unused_area", (W * L - ctx["occupied_area"]) * gap_weight)

        # Plan shape (Variant Rules)
        if archetype:
            add_archetype_constraints(
                model, archetype, vars_of(entrance_room) if entrance_room else None, side,
                ctx["hallway_slots"], W, L,
            )

        # Diversity Constraints for Variants (Must place >= 2 rooms in different zone cells)
        for v_idx, old_assignment in enumerate(exclude_zone_assignments or []):
            same_zone_bools = []
            for r_name, old_zone in old_assignment.items():
                if r_name not in specs or old_zone not in ZONE_MAP:
                    continue
                bounds = calculate_zone_bounds(W, L, old_zone)
                in_zone = model.new_bool_var(f"variant_{v_idx}_{r_name}_in_same_zone")
                # Room center in bounds
                cx2 = 2 * x_vars[r_name] + width_vars[r_name]
                cy2 = 2 * y_vars[r_name] + height_vars[r_name]
                cond1 = model.new_bool_var(f"v_{v_idx}_{r_name}_c1")
                cond2 = model.new_bool_var(f"v_{v_idx}_{r_name}_c2")
                cond3 = model.new_bool_var(f"v_{v_idx}_{r_name}_c3")
                cond4 = model.new_bool_var(f"v_{v_idx}_{r_name}_c4")

                model.add(cx2 >= 2 * bounds["x_min"]).only_enforce_if(cond1)
                model.add(cx2 < 2 * bounds["x_min"]).only_enforce_if(~cond1)
                model.add(cx2 <= 2 * bounds["x_max"]).only_enforce_if(cond2)
                model.add(cx2 > 2 * bounds["x_max"]).only_enforce_if(~cond2)
                model.add(cy2 >= 2 * bounds["y_min"]).only_enforce_if(cond3)
                model.add(cy2 < 2 * bounds["y_min"]).only_enforce_if(~cond3)
                model.add(cy2 <= 2 * bounds["y_max"]).only_enforce_if(cond4)
                model.add(cy2 > 2 * bounds["y_max"]).only_enforce_if(~cond4)

                model.add_bool_and([cond1, cond2, cond3, cond4]).only_enforce_if(in_zone)
                model.add_bool_or([~cond1, ~cond2, ~cond3, ~cond4]).only_enforce_if(~in_zone)
                same_zone_bools.append(in_zone)

            # At least 2 rooms must differ, meaning at most (total_rooms - 2) rooms can be in the same zone
            if len(same_zone_bools) >= 2:
                model.add(sum(same_zone_bools) <= len(same_zone_bools) - 2)

        return penalties

    # One straight hallway solves in under a second; several slots can use the whole time limit and
    # still return nothing. So more segments are tried only when one is proven impossible.
    slot_counts = [1, max_hallway_segments] if include_hallway and max_hallway_segments > 1 else [max_hallway_segments]
    for slots in slot_counts:
        result = solve_layout(
            plot_width=plot_width,
            plot_height=plot_height,
            room_specs=specs,
            setbacks=setbacks,
            include_hallway=include_hallway,
            layout_input=layout_input,
            require_full_coverage=fill_plot,
            max_hallway_segments=slots,
            time_limit_seconds=time_limit_seconds,
            model_extension=extension,
            relative_gap_limit=relative_gap_limit,
            verbose=False,
        )
        if result["status"] != "infeasible":
            break

    if result["status"] == "unknown":
        return {**result, "status": "timeout", "message": "Solver timed out or did not find a feasible solution.",
                "score": None}
    if result["status"] != "success":
        return {**result, "score": None}

    # Identify zone of center
    room_zones = {}
    for name, room in result["rooms"].items():
        for z_name in ZONE_MAP:
            if zone_contains(room, z_name, result["buildable_width"], result["buildable_depth"]):
                room_zones[name] = z_name
                break

    return {**result, "room_zones": room_zones, "score": result.get("score", 0)}


def is_near_duplicate(rooms_a: Dict[str, Dict[str, int]], rooms_b: Dict[str, Dict[str, int]],
                      tolerance: int = 2) -> bool:
    """Variant Rules: two layouts are the same plan if every room is within tolerance ft on every value."""
    return all(
        abs(rooms_a[name][key] - rooms_b[name][key]) <= tolerance
        for name in rooms_a for key in ("x", "y", "width", "height")
    )


def generate_variants(
    count: int = 3,
    archetypes: Tuple[Optional[str], ...] = (),
    **solve_kwargs,
) -> List[Dict[str, Any]]:
    """Day 7: Generate up to `count` distinct valid layouts, best score first.

    Tries each archetype once, then keeps solving with no archetype until there are enough. Every
    solve must place at least 2 rooms in a different zone cell, and near-duplicates are dropped.
    """
    variants = []
    assignments = []

    for archetype in list(archetypes) + [None] * count:
        if len(variants) >= count:
            break

        res = solve_with_preferences(
            exclude_zone_assignments=assignments if assignments else None,
            archetype=archetype,
            **solve_kwargs,
        )
        if res["status"] != "success":
            if archetype is None:
                break  # with no plan shape left to drop, more solves cannot succeed either
            continue

        assignments.append(res["room_zones"])
        if not any(is_near_duplicate(res["rooms"], kept["rooms"]) for kept in variants):
            variants.append({**res, "archetype": archetype})

    return sorted(variants, key=lambda v: v["score"])
