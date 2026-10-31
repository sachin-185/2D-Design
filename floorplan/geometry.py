from ortools.sat.python import cp_model
from .connections import required_pairs, add_adjacency

# Default room specifications used when no custom specifications are supplied.
DEFAULT_ROOM_SPECS = {
    "Room A": {
        "min_width": 8,
        "max_width": 12,
        "min_height": 6,
        "max_height": 10,
    },
    "Room B": {
        "min_width": 6,
        "max_width": 10,
        "min_height": 6,
        "max_height": 10,
    },
}

# Hallway configuration (MVP - provisional values)
HALLWAY_ID = "hallway_1"

HALLWAY_MIN_SHORT_SIDE = 3
HALLWAY_MAX_SHORT_SIDE = 4
HALLWAY_MIN_LONG_SIDE = 12

# Maps compass directions to drawing edges based on north orientation.
ENTRANCE_EDGE = {
    "up": {
        "N": "top",
        "E": "right",
        "S": "bottom",
        "W": "left",
    },
    "down": {
        "N": "bottom",
        "E": "left",
        "S": "top",
        "W": "right",
    },
    "left": {
        "N": "left",
        "E": "top",
        "S": "right",
        "W": "bottom",
    },
    "right": {
        "N": "right",
        "E": "bottom",
        "S": "left",
        "W": "top",
    },
}

def validate_inputs(plot_width, plot_height, room_specs):
    """Validate plot dimensions and room dimension specifications."""

    # Plot dimensions must be positive integers.
    if type(plot_width) is not int or plot_width <= 0:
        raise ValueError("Plot width must be a positive integer.")

    if type(plot_height) is not int or plot_height <= 0:
        raise ValueError("Plot height must be a positive integer.")

    # At least one room must be provided.
    if not isinstance(room_specs, dict) or not room_specs:
        raise ValueError("At least one room specification is required.")

    required_keys = {
        "min_width",
        "max_width",
        "min_height",
        "max_height",
    }

    for name, spec in room_specs.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Every room must have a non-empty name.")

        if not isinstance(spec, dict):
            raise ValueError(f"Specifications for {name} must be a dictionary.")

        if not required_keys.issubset(spec):
            raise ValueError(
                f"{name} must define minimum and maximum width and height."
            )

        for key in required_keys:
            value = spec[key]

            if type(value) is not int or value <= 0:
                raise ValueError(
                    f"{name}: {key} must be a positive integer."
                )

        if spec["min_width"] > spec["max_width"]:
            raise ValueError(
                f"{name}: minimum width cannot exceed maximum width."
            )

        if spec["min_height"] > spec["max_height"]:
            raise ValueError(
                f"{name}: minimum height cannot exceed maximum height."
            )


def check_feasibility(plot_width, plot_height, room_specs):
    """Detect basic reasons why rooms cannot fit in the plot."""

    plot_area = plot_width * plot_height

    minimum_required_area = 0

    for name, spec in room_specs.items():
        # A room's minimum dimensions must fit along each plot axis.
        if spec["min_width"] > plot_width:
            return (
                False,
                f"{name} requires a minimum width of "
                f"{spec['min_width']} ft, but the plot is only "
                f"{plot_width} ft wide.",
            )

        if spec["min_height"] > plot_height:
            return (
                False,
                f"{name} requires a minimum height of "
                f"{spec['min_height']} ft, but the plot is only "
                f"{plot_height} ft deep.",
            )

        # Add the smallest possible area of this room.
        minimum_required_area += (
            spec["min_width"] * spec["min_height"]
        )

    # Non-overlapping rooms cannot occupy more area than the plot.
    if minimum_required_area > plot_area:
        return (
            False,
            f"Rooms require at least {minimum_required_area} sq ft, "
            f"but the plot has only {plot_area} sq ft.",
        )

    return True, "Basic feasibility checks passed."


def calculate_buildable_area(plot_width, plot_height, setbacks):
    """Calculate the rectangular buildable area after setbacks."""

    # 1. Validate the plot dimensions.
    if type(plot_width) is not int or plot_width <= 0:
        raise ValueError("Plot width must be a positive integer.")

    if type(plot_height) is not int or plot_height <= 0:
        raise ValueError("Plot height must be a positive integer.")

    # 2. Validate the setbacks dictionary.
    required_setbacks = {"left", "right", "front", "back"}

    if (
        not isinstance(setbacks, dict)
        or set(setbacks.keys()) != required_setbacks
    ):
        raise ValueError(
            "Setbacks must contain exactly: left, right, front, and back."
        )

    # 3. Every setback must be a non-negative integer.
    for side, value in setbacks.items():
        if type(value) is not int or value < 0:
            raise ValueError(
                f"The {side} setback must be a non-negative integer."
            )

    # 4. Extract the validated values.
    left = setbacks["left"]
    right = setbacks["right"]
    front = setbacks["front"]
    back = setbacks["back"]

    # 5. Calculate the remaining buildable dimensions.
    buildable_width = plot_width - left - right
    buildable_depth = plot_height - front - back

    # 6. Reject setbacks that eliminate the buildable area.
    if buildable_width <= 0 or buildable_depth <= 0:
        raise ValueError(
            "Setbacks leave no positive buildable area. "
            "Reduce the setbacks or increase the plot dimensions."
        )

    # 7. Return dimensions and the buildable area's origin.
    return {
        "width": buildable_width,
        "depth": buildable_depth,
        "offset_x": left,
        "offset_y": front,
    }


def solve_layout(
    plot_width=20,
    plot_height=12,
    room_specs=None,
    setbacks=None,
    include_hallway=False,
    layout_input=None,
    require_full_coverage=False,
):
    # 1. Set default room specifications.
    if room_specs is None:
        room_specs = DEFAULT_ROOM_SPECS

    # 2. Set default setbacks to zero.
    if setbacks is None:
        setbacks = {
            "left": 0,
            "right": 0,
            "front": 0,
            "back": 0,
        }

    # 3. Validate plot dimensions and room specifications.
    validate_inputs(plot_width, plot_height, room_specs)

    # 4. Validate the setback inputs.
    required_setbacks = {"left", "right", "front", "back"}

    if (
        not isinstance(setbacks, dict)
        or set(setbacks.keys()) != required_setbacks
    ):
        raise ValueError(
            "Setbacks must contain exactly: left, right, front, and back."
        )

    for side, value in setbacks.items():
        if type(value) is not int or value < 0:
            raise ValueError(
                f"The {side} setback must be a non-negative integer."
            )

    # 5. Calculate the area available for room placement.
    buildable = calculate_buildable_area(
        plot_width, plot_height, setbacks
    )

    buildable_width = buildable["width"]
    buildable_depth = buildable["depth"]

    # 6. Check feasibility against the buildable area.
    feasible, message = check_feasibility(
        buildable_width, buildable_depth, room_specs
    )

    # Shared information included in every solver result.
    result_info = {
        "plot_width": plot_width,
        "plot_height": plot_height,
        "buildable_width": buildable_width,
        "buildable_depth": buildable_depth,
        "setbacks": setbacks,
        "buildable_offset_x": buildable["offset_x"],
        "buildable_offset_y": buildable["offset_y"],
    }

    if not feasible:
        return {
            **result_info,
            "status": "infeasible",
            "message": message,
            "rooms": None,
        }

    # 7. Create the OR-Tools constraint model.
    model = cp_model.CpModel()

    x_vars = {}
    y_vars = {}
    width_vars = {}
    height_vars = {}

    x_intervals = []
    y_intervals = []

    # 8. Create position, dimension, and boundary constraints.
    for name, spec in room_specs.items():
        x = model.new_int_var(
            0, buildable_width, f"{name}_x"
        )
        y = model.new_int_var(
            0, buildable_depth, f"{name}_y"
        )

        width = model.new_int_var(
            spec["min_width"],
            spec["max_width"],
            f"{name}_width",
        )
        height = model.new_int_var(
            spec["min_height"],
            spec["max_height"],
            f"{name}_height",
        )

        # Keep the room inside the buildable rectangle.
        model.add(x + width <= buildable_width)
        model.add(y + height <= buildable_depth)

        # Calculate the room's right and top edges.
        x_end = model.new_int_var(
            0, buildable_width, f"{name}_x_end"
        )
        y_end = model.new_int_var(
            0, buildable_depth, f"{name}_y_end"
        )

        model.add(x_end == x + width)
        model.add(y_end == y + height)

        # Represent the room's horizontal and vertical extents.
        x_interval = model.new_interval_var(
            x, width, x_end, f"{name}_x_interval"
        )
        y_interval = model.new_interval_var(
            y, height, y_end, f"{name}_y_interval"
        )

        x_vars[name] = x
        y_vars[name] = y
        width_vars[name] = width
        height_vars[name] = height

        x_intervals.append(x_interval)
        y_intervals.append(y_interval)

    hallway_vars = None

    if include_hallway:    
        # 9. Create variables for the single MVP hallway.
        hallway_vars = {
            "x": model.new_int_var(
                0, buildable_width, "hallway_1_x"
            ),
            "y": model.new_int_var(
                0, buildable_depth, "hallway_1_y"
            ),
            "w": model.new_int_var(
                1, buildable_width, "hallway_1_width"
            ),
            "h": model.new_int_var(
                1, buildable_depth, "hallway_1_height"
            ),
        }

        # Calculate the hallway's right and top edges.
        hallway_x_end = model.new_int_var(
            0, buildable_width, "hallway_1_x_end"
        )

        hallway_y_end = model.new_int_var(
            0, buildable_depth, "hallway_1_y_end"
        )

        model.add(
            hallway_x_end == hallway_vars["x"] + hallway_vars["w"]
        )

        model.add(
            hallway_y_end == hallway_vars["y"] + hallway_vars["h"]
        )

        # Enforce hallway boundary constraints.
        model.add(hallway_vars["x"] >= 0)
        model.add(hallway_vars["y"] >= 0)

        model.add(
            hallway_vars["x"] + hallway_vars["w"]
            <= buildable_width
        )

        model.add(
            hallway_vars["y"] + hallway_vars["h"]
            <= buildable_depth
        )

        # Represent the hallway's horizontal and vertical extents.
        hallway_x_interval = model.new_interval_var(
            hallway_vars["x"],
            hallway_vars["w"],
            hallway_x_end,
            "hallway_1_x_interval",
        )

        hallway_y_interval = model.new_interval_var(
            hallway_vars["y"],
            hallway_vars["h"],
            hallway_y_end,
            "hallway_1_y_interval",
        )

        # Include hallway intervals in the non-overlap model.
        x_intervals.append(hallway_x_interval)
        y_intervals.append(hallway_y_interval)

        # 10. Enforce hallway dimensions and orientation.

        # Boolean variables representing the two possible orientations.
        horizontal = model.new_bool_var("hallway_horizontal")
        vertical = model.new_bool_var("hallway_vertical")

        # Horizontal hallway:
        # Width = long side, height = short side.
        model.add(
            hallway_vars["w"] >= HALLWAY_MIN_LONG_SIDE
        ).only_enforce_if(horizontal)

        model.add(
            hallway_vars["h"] >= HALLWAY_MIN_SHORT_SIDE
        ).only_enforce_if(horizontal)

        model.add(
            hallway_vars["h"] <= HALLWAY_MAX_SHORT_SIDE
        ).only_enforce_if(horizontal)

        # Vertical hallway:
        # Height = long side, width = short side.
        model.add(
            hallway_vars["h"] >= HALLWAY_MIN_LONG_SIDE
        ).only_enforce_if(vertical)

        model.add(
            hallway_vars["w"] >= HALLWAY_MIN_SHORT_SIDE
        ).only_enforce_if(vertical)

        model.add(
            hallway_vars["w"] <= HALLWAY_MAX_SHORT_SIDE
        ).only_enforce_if(vertical)

        # At least one orientation must be selected.
        model.add_bool_or([horizontal, vertical])

    # 11. Create a variable mapping compatible with P4's functions.
    if include_hallway:

        if layout_input is None:
            raise ValueError(
                "layout_input is required when include_hallway=True"
            )

        room_variables = {
            name: {
                "x": x_vars[name],
                "y": y_vars[name],
                "w": width_vars[name],
                "h": height_vars[name],
            }
            for name in room_specs
        }

        # Add hallway variables to the same mapping.
        room_variables[HALLWAY_ID] = hallway_vars

    # 12. Add required adjacency constraints from P4.
    if include_hallway:

        pairs = required_pairs(layout_input)

        for i, (a, b) in enumerate(pairs):

            if a not in room_variables or b not in room_variables:
                raise ValueError(
                    f"Invalid adjacency pair: {a}, {b}. "
                    "One or both rooms are missing from solver variables."
                )

            add_adjacency(
                model,
                room_variables[a],
                room_variables[b],
                3,
                buildable_width,
                buildable_depth,
                f"adj{i}",
            )

    # 13. Identify the living room for entrance-side placement.
    if include_hallway:

        living_rooms = [
            room
            for room in layout_input["rooms"]
            if room["type"] == "living"
        ]

        if not living_rooms:
            raise ValueError(
                "At least one living room is required for entrance placement."
            )

        living_name = living_rooms[0]["name"]
        living_vars = room_variables[living_name]

        # Get entrance direction and north orientation.
        entrance = layout_input.get("entrance", "S")
        north = layout_input.get("north", "up")

        # Validate the supplied directions.
        if north not in ENTRANCE_EDGE:
            raise ValueError(
                f"Invalid north orientation: {north}"
            )

        if entrance not in ENTRANCE_EDGE[north]:
            raise ValueError(
                f"Invalid entrance direction: {entrance}"
            )

        # Convert compass direction into drawing edge.
        entrance_edge = ENTRANCE_EDGE[north][entrance]

        # Force the living room to touch the selected entrance boundary.
        if entrance_edge == "bottom":
            model.add(living_vars["y"] == 0)

        elif entrance_edge == "top":
            model.add(
                living_vars["y"] + living_vars["h"]
                == buildable_depth
            )

        elif entrance_edge == "left":
            model.add(living_vars["x"] == 0)

        elif entrance_edge == "right":
            model.add(
                living_vars["x"] + living_vars["w"]
                == buildable_width
            )

    # 14. Create area variables for all rooms and hallway.
    buildable_area_total = buildable_width * buildable_depth

    room_area_vars = {}

    for name in room_specs:

        room_area = model.new_int_var(
            0,
            buildable_area_total,
            f"{name}_area",
        )

        model.add_multiplication_equality(
            room_area,
            [width_vars[name], height_vars[name]],
        )

        room_area_vars[name] = room_area

    if include_hallway:

        hallway_area = model.new_int_var(
            0,
            buildable_area_total,
            "hallway_area",
        )

        model.add_multiplication_equality(
            hallway_area,
            [hallway_vars["w"], hallway_vars["h"]],
        )
        
    if include_hallway and require_full_coverage:

        total_occupied_area = (
            sum(room_area_vars.values()) + hallway_area
        )

        model.add(
            total_occupied_area == buildable_area_total
        )
    # 13. Prevent rooms from overlapping.
    model.add_no_overlap_2d(x_intervals, y_intervals)

    # 14. Solve the model.
    solver = cp_model.CpSolver()
    status = solver.solve(model)

    #Temporary Inclusion <>
    print("\n--- OPTIMIZATION DIAGNOSTICS ---")
    print("Solver status:", solver.status_name(status))

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("Occupied area:", solver.objective_value, "sq ft")
        print("Best objective bound:", solver.best_objective_bound, "sq ft")
    #<>
    
    if status == cp_model.INFEASIBLE:
        return {
            **result_info,
            "status": "infeasible",
            "message": (
                "No arrangement satisfies all geometry constraints."
            ),
            "rooms": None,
        }

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            **result_info,
            "status": "unknown",
            "message": "The solver did not find a solution.",
            "rooms": None,
        }

    # 15. Extract the solution as structured data.
    rooms = {}

    for name in room_specs:
        x = solver.value(x_vars[name])
        y = solver.value(y_vars[name])
        width = solver.value(width_vars[name])
        height = solver.value(height_vars[name])

        rooms[name] = {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "w": width,
            "h": height,
            "area": width * height,
        }

    # Extract hallway solution when hallway mode is enabled.
    hallway_result = None

    if include_hallway:

        hallway_x = solver.value(hallway_vars["x"])
        hallway_y = solver.value(hallway_vars["y"])
        hallway_w = solver.value(hallway_vars["w"])
        hallway_h = solver.value(hallway_vars["h"])

        hallway_result = {
            "id": HALLWAY_ID,
            "x": hallway_x,
            "y": hallway_y,
            "w": hallway_w,
            "h": hallway_h,
            "area": hallway_w * hallway_h,
        }

    return {
        **result_info,
        "status": "success",
        "message": "A valid layout was found.",
        "rooms": rooms,
        **(
            {"hallway": hallway_result}
            if include_hallway
            else {}
        ),
    }


def read_positive_integer(prompt):
    """Read a positive integer from the terminal."""
    while True:
        raw_value = input(prompt)

        try:
            value = int(raw_value)
        except ValueError:
            print("Please enter a whole number, such as 20.")
            continue

        if value <= 0:
            print("The value must be greater than zero.")
            continue

        return value


if __name__ == "__main__":
    print("=== Two-Room Floor Plan Solver ===")

    plot_width = read_positive_integer("Enter plot width (ft): ")
    plot_height = read_positive_integer("Enter plot height (ft): ")

    try:
        result = solve_layout(
            plot_width=plot_width,
            plot_height=plot_height,
        )
    except ValueError as error:
        print(f"Invalid input: {error}")
    else:
        if result["status"] != "success":
            print(f"\nStatus: {result['status']}")
            print(f"Reason: {result['message']}")
        else:
            print(f"\nStatus: {result['status']}")
            print(result["message"])
            print(
                f"Buildable area: {result['plot_width']} x "
                f"{result['plot_height']} ft"
            )

            for name, room in result["rooms"].items():
                print(f"\n{name}:")
                print(f"  Position: ({room['x']}, {room['y']})")
                print(
                    f"  Dimensions: {room['width']} x "
                    f"{room['height']} ft"
                )
                print(f"  Area: {room['area']} sq ft")

