
from ortools.sat.python import cp_model


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

def solve_two_rooms(plot_width=20, plot_height=12, room_specs=None):
    # 1. Use the default room specifications or the caller's custom ones.
    if room_specs is None:
        room_specs = DEFAULT_ROOM_SPECS

    # Validate inputs before creating the solver model.
    validate_inputs(plot_width, plot_height, room_specs)

    # Check whether the request is obviously impossible.
    feasible, message = check_feasibility(
        plot_width, plot_height, room_specs
    )

    if not feasible:
        print(f"Feasibility check failed: {message}")
        return None

    # Create the constraint model.
    model = cp_model.CpModel()

    x_vars = {}
    y_vars = {}
    width_vars = {}
    height_vars = {}

    x_intervals = []
    y_intervals = []

    # 3. Create variables and constraints for every room.
    for name, spec in room_specs.items():
        x = model.new_int_var(0, plot_width, f"{name}_x")
        y = model.new_int_var(0, plot_height, f"{name}_y")

        width = model.new_int_var(
            spec["min_width"], spec["max_width"], f"{name}_width"
        )
        height = model.new_int_var(
            spec["min_height"], spec["max_height"], f"{name}_height"
        )

        # Each room must remain inside the buildable area.
        model.add(x + width <= plot_width)
        model.add(y + height <= plot_height)

        # Define the ending coordinates of the room.
        x_end = model.new_int_var(0, plot_width, f"{name}_x_end")
        y_end = model.new_int_var(0, plot_height, f"{name}_y_end")

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

    # 4. Prevent rooms from overlapping.
    model.add_no_overlap_2d(x_intervals, y_intervals)

    # 5. Find a valid arrangement.
    solver = cp_model.CpSolver()
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    # 6. Return the solution as structured data.
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
            "area": width * height,
        }

    return {
        "plot_width": plot_width,
        "plot_height": plot_height,
        "rooms": rooms,
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
        result = solve_two_rooms(
            plot_width=plot_width,
            plot_height=plot_height,
        )
    except ValueError as error:
        print(f"Invalid input: {error}")
    else:
        if result is None:
            print("No valid layout was found.")
        else:
            print(
                f"\nBuildable area: {result['plot_width']} x "
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
