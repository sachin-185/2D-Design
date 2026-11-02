"""One call that runs every check on a finished layout (P4).

    problems = validate_all(inp, layout)      # [] means the layout is good

Layers: geometry (inside plot, overlap, sizes, gaps, hallway shape, entrance wall), adjacency
(required connections), connectivity (reachability) and forbidden patterns (F1 so far; F2 to F4 need door positions from P5).
"""
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
    """The room you walk into from outside: the first living room, else the first room listed."""
    for r in inp["rooms"]:
        if r["type"] == "living":
            return r["name"]
    return inp["rooms"][0]["name"]


def validate_all(inp, layout, size_table=SIZE_TABLE, check_gaps=True, door_min=DOOR_MIN):
    bad_input = check_input(inp)
    if bad_input:  # the other checks need a usable input, so report only these
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


def errors_only(problems):
    """Problems that make a layout invalid. A problem without a severity counts as an error."""
    return [p for p in problems if p.get("severity", "error") == "error"]


def warnings_only(problems):
    """Problems that are reported but do not make a layout invalid (for example unused area)."""
    return [p for p in problems if p.get("severity", "error") == "warning"]


def is_valid(problems):
    """A layout is valid when it has no errors. Warnings are allowed."""
    return not errors_only(problems)


def adapt_solver_result(solver_result):
    """
    Convert P1 solver output into the layout format expected by P4.
    P1: rooms are stored in a dictionary.
    P4: rooms are expected as a list of dictionaries.
    """
    # Safety check: only validate successful solver results.
    if solver_result.get("status") != "success":
        raise ValueError(
            "Cannot validate an unsuccessful solver result."
        )

    rooms_by_name = solver_result.get("rooms")

    if not isinstance(rooms_by_name, dict):
        raise ValueError(
            "Solver result must contain a successful rooms dictionary."
        )

    rooms = []

    for name, data in rooms_by_name.items():
        rooms.append({
            "name": name,
            "x": data["x"],
            "y": data["y"],
            "w": data.get("w", data.get("width")),
            "h": data.get("h", data.get("height")),
        })

    layout = {"rooms": rooms}

    segments = solver_result.get("hallway_segments")

    if segments:
        layout["hallway_segments"] = segments

        # Backward compatibility for a single hallway
        if len(segments) == 1:
            layout["hallway"] = segments[0]

    elif solver_result.get("hallway") is not None:
        layout["hallway"] = solver_result["hallway"]

    return layout

def validate_solver_result(
    inp,
    solver_result,
    size_table=SIZE_TABLE,
    check_gaps=True,
    door_min=DOOR_MIN,
):
    """
    Adapt P1 solver output and run P4's complete validation.
    """
    layout = adapt_solver_result(solver_result)

    return validate_all(
        inp,
        layout,
        size_table=size_table,
        check_gaps=check_gaps,
        door_min=door_min,
    )