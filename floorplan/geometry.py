from ortools.sat.python import cp_model


def solve_two_rooms():
    # 1. Define the buildable area in feet.
    plot_width = 20
    plot_height = 12

    # 2. Define the allowed dimensions for each room.
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

    # 3. Create the constraint programming model.
    model = cp_model.CpModel()

    x_vars = {}
    y_vars = {}
    width_vars = {}
    height_vars = {}

    x_intervals = []
    y_intervals = []

    # 4. Create variables and constraints for every room.
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

        
        # Calculate the ending coordinates of each room.
        x_end = model.new_int_var(0, plot_width, f"{name}_x_end")
        y_end = model.new_int_var(0, plot_height, f"{name}_y_end")

        model.add(x_end == x + width)
        model.add(y_end == y + height)

        # Intervals describe each room's horizontal and vertical extent.
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

    # 5. The rooms must not overlap.
    model.add_no_overlap_2d(x_intervals, y_intervals)

    # 6. Ask the solver to find a valid arrangement.
    solver = cp_model.CpSolver()
    status = solver.solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("A valid floor layout was found!")
        print(f"Buildable area: {plot_width} ft x {plot_height} ft\n")

        for name in room_specs:
            x = solver.value(x_vars[name])
            y = solver.value(y_vars[name])
            width = solver.value(width_vars[name])
            height = solver.value(height_vars[name])

            print(f"{name}:")
            print(f"  Position: x={x}, y={y}")
            print(f"  Dimensions: {width} ft x {height} ft")
            print(f"  Area: {width * height} sq ft\n")
    else:
        print("No valid arrangement was found.")


if __name__ == "__main__":
    solve_two_rooms()
