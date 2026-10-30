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
    check_no_gaps,
    check_reachability,
    check_required_connections,
)

from floorplan.validator import (
    SIZE_TABLE,
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
    entrance = entrance_room_name(inp)
    found = check_inside_plot(inp, layout) + check_no_overlap(layout)
    found += check_size_limits(inp, layout, size_table)
    found += check_hallway_shape(layout)
    found += check_entrance_wall(inp, layout)
    found += check_required_connections(inp, layout, door_min)
    found += check_reachability(layout, entrance, door_min)
    found += check_bedroom_through_bedroom(inp, layout, entrance, door_min)
    if check_gaps:
        found += check_no_gaps(inp, layout)
    return found
