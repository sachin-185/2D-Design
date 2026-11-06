
"""
Convert JSON floor-plan input into arguments for the P1 geometry solver.

Room dimensions are injected through room_size_table.
Do not put temporary or unconfirmed production dimensions in this module.
"""


def build_room_specs(input_data, room_size_table):
    """
    Build the room_specs dictionary expected by solve_layout().

    room_size_table format:
    {
        "living": ([12, 12], [20, 20]),
        "bedroom": ([10, 10], [16, 16])
    }

    Each entry is:
        (minimum_dimensions, maximum_dimensions)

    Dimensions are represented as [width, height].
    """

    room_specs = {}

    for room in input_data["rooms"]:
        name = room["name"]
        room_type = room["type"]

        if room_type not in room_size_table:
            raise ValueError(
                f"No room dimensions configured for type: {room_type}"
            )

        base_min, base_max = room_size_table[room_type]

        # Copy the configured dimensions so that we do not
        # accidentally modify the original configuration.
        min_dimensions = list(base_min)
        max_dimensions = list(base_max)

        # Custom minimum dimensions override the configured minimum.
        if "min" in room:
            min_dimensions = list(room["min"])

        # Custom maximum dimensions override the configured maximum.
        if "max" in room:
            max_dimensions = list(room["max"])

        if len(min_dimensions) != 2 or len(max_dimensions) != 2:
            raise ValueError(
                f"Invalid dimensions for room: {name}"
            )

        min_width, min_height = min_dimensions
        max_width, max_height = max_dimensions

        if min_width > max_width or min_height > max_height:
            raise ValueError(
                f"Minimum dimensions exceed maximum dimensions for room: {name}"
            )

        room_specs[name] = {
            "min_width": min_width,
            "max_width": max_width,
            "min_height": min_height,
            "max_height": max_height,
        }

    return room_specs


def build_solver_arguments(input_data, room_size_table):
    """
    Convert JSON input into keyword arguments for solve_layout().

    This prepares geometry inputs only. For zones, pins and scoring
    use build_preference_arguments().
    """

    plot = input_data["plot"]

    if len(plot) != 2:
        raise ValueError(
            "Plot must contain exactly [width, length]"
        )

    plot_width, plot_height = plot

    # Missing setbacks default to zero.
    input_setbacks = input_data.get("setbacks", {})

    setbacks = {
        "left": input_setbacks.get("left", 0),
        "right": input_setbacks.get("right", 0),
        "front": input_setbacks.get("front", 0),
        "back": input_setbacks.get("back", 0),
    }

    room_specs = build_room_specs(
        input_data,
        room_size_table
    )

    # Preserve the original room definitions as metadata.
    # The geometry solver uses name, type, and attached_to.
    # Zones and pins are not enforced by solve_layout alone.
    # build_preference_arguments() below adds them for P2's solver.
    layout_input = {
        "rooms": [
            {
                "name": room["name"],
                "type": room["type"],
                **(
                    {"zone": room["zone"]}
                    if "zone" in room else {}
                ),
                **(
                    {"zone_mode": room["zone_mode"]}
                    if "zone_mode" in room else {}
                ),
                **(
                    {"attached_to": room["attached_to"]}
                    if "attached_to" in room else {}
                ),
            }
            for room in input_data["rooms"]
        ],
        "entrance": input_data["entrance"],
        "north": input_data.get("north", "up"),
    }

    return {
        "plot_width": plot_width,
        "plot_height": plot_height,
        "room_specs": room_specs,
        "setbacks": setbacks,
        "include_hallway": True,
        "layout_input": layout_input,
    }


# Room types with a required connection in required_pairs(). Any other type only has to be reachable.
CONNECTED_TYPES = ("living", "bedroom", "bathroom", "kitchen")

# Points per unused sq ft. Larger than the other penalties so the plan fills the plot first.
GAP_WEIGHT = 20


def build_preferred_adjacencies(input_data):
    """Pairs of rooms that should be close (S4). They are not hard rules."""
    names = {}
    for room in input_data["rooms"]:
        names.setdefault(room["type"], []).append(room["name"])

    pairs = []
    for room in input_data["rooms"]:
        if room["type"] == "bathroom" and not room.get("attached_to"):
            pairs += [(room["name"], bedroom) for bedroom in names.get("bedroom", [])]
    for dining in names.get("dining", []):
        pairs += [(dining, kitchen) for kitchen in names.get("kitchen", [])]
        pairs += [(dining, living) for living in names.get("living", [])[:1]]
    return pairs


def build_preference_arguments(input_data, room_size_table, preferred_sizes=None):
    """
    Convert JSON input into keyword arguments for P2's solve_with_preferences().

    preferred_sizes is {room_type: (width, height)} for the S1 penalty.
    """
    args = build_solver_arguments(input_data, room_size_table)
    specs = args["room_specs"]
    preferred_sizes = preferred_sizes or {}

    preferences = {}
    for room in input_data["rooms"]:
        spec = specs[room["name"]]
        # The checker compares sides shortest to shortest, so a room may be turned.
        spec["rotatable"] = (
            spec["min_width"] != spec["min_height"]
            or spec["max_width"] != spec["max_height"]
        )
        if room["type"] in preferred_sizes:
            spec["pref_width"], spec["pref_height"] = preferred_sizes[room["type"]]
        if room.get("zone"):
            preferences[room["name"]] = {
                "zone": room["zone"],
                "zone_mode": room.get("zone_mode", "try"),
            }

    pins = {}
    for pin in input_data.get("pins", []):
        pins[pin["room"]] = {
            side: pin[side] for side in ("width", "height") if pin.get(side) is not None
        }

    return {
        "plot_width": args["plot_width"],
        "plot_height": args["plot_height"],
        "room_specs": specs,
        "setbacks": args["setbacks"],
        "include_hallway": True,
        "layout_input": args["layout_input"],
        "preferences": preferences,
        "preferred_adjacencies": build_preferred_adjacencies(input_data),
        "pinned_dimensions": pins or None,
        "entrance": input_data["entrance"],
        "north": input_data.get("north", "up"),
        "entrance_room": next(
            (r["name"] for r in input_data["rooms"] if r["type"] == "living"), None
        ),
        "must_connect": [
            r["name"] for r in input_data["rooms"] if r["type"] not in CONNECTED_TYPES
        ],
        "gap_weight": GAP_WEIGHT,
    }


def build_no_hallway_arguments(args, input_data):
    """
    The same request for a layout with no hallway (connection_rules.md, item 8).

    Everything opens off the first living room, or its bedroom for an attached bathroom.
    With no hallway P1 adds no connections, so they are listed here.
    """
    living = args["entrance_room"]
    pairs = []
    for room in input_data["rooms"]:
        if room["name"] == living or room["type"] not in CONNECTED_TYPES + ("living",):
            continue
        pairs.append((room["name"], room.get("attached_to") or living))

    return {
        **args,
        "include_hallway": False,
        "layout_input": None,
        "required_adjacencies": pairs,
        "entrance_wall": True,
    }
