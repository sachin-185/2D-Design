
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

    This initial version prepares geometry inputs.
    Pin and zone enforcement will be implemented separately.
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
    # The current geometry solver uses name and type.
    # Zone and pin constraints are not enforced by this adapter yet.
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
