
"""One call that runs every check on a finished layout."""

from floorplan.connections_check import (
    DOOR_MIN,
    check_bedroom_through_bedroom,
    check_entrance_wall,
    check_hallway_shape,
    check_hallway_connectivity,
    check_no_gaps,
    check_reachability,
    check_required_connections,
    check_no_5x5_hallway_square,
)

from floorplan.validator import (
    SIZE_TABLE,
    check_input,
    check_inside_plot,
    check_no_overlap,
    check_size_limits,
)


def entrance_room_name(inp):
    """Return the first living room, or the first room if none exists."""
    for room in inp["rooms"]:
        if room["type"] == "living":
            return room["name"]
    return inp["rooms"][0]["name"]


def validate_all(inp, layout, size_table=SIZE_TABLE, check_gaps=True, door_min=DOOR_MIN):
    """Run all input, geometry, adjacency and connectivity checks."""

    # Validate input before running geometric and connectivity checks.
    bad_input = check_input(inp)

    if bad_input:
        return bad_input

    entrance = entrance_room_name(inp)

    found = check_inside_plot(inp, layout) + check_no_overlap(layout)
    found += check_size_limits(inp, layout, size_table)
    found += check_hallway_shape(layout)
    found += check_no_5x5_hallway_square(layout)

    found += check_hallway_connectivity(layout, door_min)
    found += check_entrance_wall(inp, layout)
    found += check_required_connections(inp, layout, door_min)
    found += check_reachability(layout, entrance, door_min)
    found += check_bedroom_through_bedroom(inp, layout, entrance, door_min)

    if check_gaps:
        found += check_no_gaps(inp, layout)

    return found


def adapt_solver_result(solver_result):
    """
    Convert P1 solver output into the layout format expected by P4.

    P1 stores rooms in a dictionary; P4 expects a list of dictionaries.
    Validate the structure before converting it.
    """

    if not isinstance(solver_result, dict):
        raise ValueError("Solver result must be a dictionary.")

    if solver_result.get("status") != "success":
        raise ValueError("Cannot validate an unsuccessful solver result.")

    rooms_by_name = solver_result.get("rooms")

    if not isinstance(rooms_by_name, dict):
        raise ValueError(
            "Solver result must contain a successful rooms dictionary."
        )

    def validate_rectangle(data, label):
        if not isinstance(data, dict):
            raise ValueError(f"{label} must be a dictionary")

        values = {}

        # Coordinates must be whole numbers.
        for field in ("x", "y"):
            value = data.get(field)

            if type(value) is not int:
                raise ValueError(
                    f"{label} needs a whole number '{field}'"
                )

            values[field] = value

        # Accept both short and long dimension names.
        for field, alias in (("w", "width"), ("h", "height")):
            value = data.get(field, data.get(alias))

            if type(value) is not int:
                raise ValueError(
                    f"{label} needs a whole number '{field}'"
                )

            values[field] = value

        if values["w"] <= 0 or values["h"] <= 0:
            raise ValueError(
                f"{label} needs positive width and height"
            )

        return values

    # Validate and convert rooms.
    rooms = []

    for name, data in rooms_by_name.items():
        rect = validate_rectangle(data, f"room '{name}'")

        rooms.append({
            "name": name,
            **rect
        })

    layout = {"rooms": rooms}

    # Validate multiple hallway segments, if supplied.
    if "hallway_segments" in solver_result:
        segments = solver_result["hallway_segments"]

        if not isinstance(segments, list):
            raise ValueError("'hallway_segments' must be a list")

        if segments:
            validated_segments = []

            for index, segment in enumerate(segments, start=1):
                rect = validate_rectangle(
                    segment,
                    f"hallway segment {index}"
                )

                # Preserve additional fields such as id and area.
                validated_segments.append({
                    **segment,
                    **rect
                })

            layout["hallway_segments"] = validated_segments

            # Backward compatibility for a single hallway.
            if len(validated_segments) == 1:
                layout["hallway"] = validated_segments[0]

    # Support the older single-hallway format.
    elif solver_result.get("hallway") is not None:
        hallway = solver_result["hallway"]

        rect = validate_rectangle(hallway, "hallway")

        layout["hallway"] = {
            **hallway,
            **rect
        }

    return layout


def validate_solver_result(
    inp,
    solver_result,
    size_table=SIZE_TABLE,
    check_gaps=True,
    door_min=DOOR_MIN,
):
    """Adapt P1 solver output and run P4's complete validation."""

    layout = adapt_solver_result(solver_result)

    return validate_all(
        inp,
        layout,
        size_table=size_table,
        check_gaps=check_gaps,
        door_min=door_min,
    )


def errors_only(problems):
    """Return only errors. Missing severity defaults to error."""
    return [
        problem for problem in problems
        if problem.get("severity", "error") == "error"
    ]


def warnings_only(problems):
    """Return only warnings."""
    return [
        problem for problem in problems
        if problem.get("severity", "error") == "warning"
    ]


def is_valid(problems):
    """Warnings are allowed; errors make a layout invalid."""
    return not errors_only(problems)
