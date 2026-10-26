from ortools.sat.python import cp_model


def solve_two_rooms():
    # 1. Define the buildable area in feet.
    plot_width = 20
    plot_height = 12

    # 2. Define allowed dimensions for each room.
    room_specs = {
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

    # 3. Create the constraint model.
    model = cp_model.CpModel()

    x_vars = {}
    y_vars = {}
    width_vars = {}
    height_vars = {}

    x_intervals = []
    y_intervals = []

    # 4. Create variables and constraints for each room.
    for name, spec in room_specs.items():
        x = model.new_int_var(0, plot_width, f"{name}_x")
        y = model.new_int_var(0, plot_height, f"{name}_y")

        width = model.new_int_var(
            spec["min_width"], spec["max_width"], f"{name}_width"
        )
        height = model.new_int_var(
            spec["min_height"], spec["max_height"], f"{name}_height"
        )

        # Keep each room inside the buildable area.
        model.add(x + width <= plot_width)
        model.add(y + height <= plot_height)

        # Define explicit end coordinates.
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

    # 5. Prevent rooms from overlapping.
    model.add_no_overlap_2d(x_intervals, y_intervals)

    # 6. Solve the model.
    solver = cp_model.CpSolver()
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    # 7. Return structured layout data instead of printing it.
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


if __name__ == "__main__":
    result = solve_two_rooms()

    if result is None:
        print("No valid arrangement was found.")
    else:
        print("A valid floor layout was found!")
        print(
            f"Buildable area: {result['plot_width']} ft "
            f"x {result['plot_height']} ft\n"
        )

        for name, room in result["rooms"].items():
            print(f"{name}:")
            print(f"  Position: x={room['x']}, y={room['y']}")
            print(
                f"  Dimensions: {room['width']} ft "
                f"x {room['height']} ft"
            )
            print(f"  Area: {room['area']} sq ft\n")
