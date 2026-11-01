"""CP-SAT floor-plan geometry solver with connected multi-segment hallways."""

import time
from ortools.sat.python import cp_model

from .connections import add_adjacency, required_pairs

DEFAULT_ROOM_SPECS = {
    "Room A": {"min_width": 8, "max_width": 12, "min_height": 6, "max_height": 10},
    "Room B": {"min_width": 6, "max_width": 10, "min_height": 6, "max_height": 10},
}

HALLWAY_ID = "hallway_1"
HALLWAY_MIN_SHORT_SIDE = 3
HALLWAY_MAX_SHORT_SIDE = 4
HALLWAY_MIN_TOTAL_LENGTH = 12
HALLWAY_MAX_SEGMENTS = 6
HALLWAY_ROOM_WALL_MIN = 3
HALLWAY_NETWORK_WALL_MIN = 3

ENTRANCE_EDGE = {
    "up": {"N": "top", "E": "right", "S": "bottom", "W": "left"},
    "down": {"N": "bottom", "E": "left", "S": "top", "W": "right"},
    "left": {"N": "left", "E": "top", "S": "right", "W": "bottom"},
    "right": {"N": "right", "E": "bottom", "S": "left", "W": "top"},
}


def validate_inputs(plot_width, plot_height, room_specs):
    if type(plot_width) is not int or plot_width <= 0:
        raise ValueError("Plot width must be a positive integer.")
    if type(plot_height) is not int or plot_height <= 0:
        raise ValueError("Plot height must be a positive integer.")
    if not isinstance(room_specs, dict) or not room_specs:
        raise ValueError("At least one room specification is required.")

    required = {"min_width", "max_width", "min_height", "max_height"}
    for name, spec in room_specs.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Every room must have a non-empty name.")
        if not isinstance(spec, dict) or not required.issubset(spec):
            raise ValueError(f"{name} must define minimum and maximum width and height.")
        for key in required:
            if type(spec[key]) is not int or spec[key] <= 0:
                raise ValueError(f"{name}: {key} must be a positive integer.")
        if spec["min_width"] > spec["max_width"]:
            raise ValueError(f"{name}: minimum width cannot exceed maximum width.")
        if spec["min_height"] > spec["max_height"]:
            raise ValueError(f"{name}: minimum height cannot exceed maximum height.")


def check_feasibility(plot_width, plot_height, room_specs):
    """Basic axis-aligned feasibility check before building the CP-SAT model."""
    minimum_area = 0
    for name, spec in room_specs.items():
        if spec["min_width"] > plot_width:
            return False, (
                f"{name} requires a minimum width of {spec['min_width']} ft, "
                f"but the buildable area is only {plot_width} ft wide."
            )
        if spec["min_height"] > plot_height:
            return False, (
                f"{name} requires a minimum height of {spec['min_height']} ft, "
                f"but the buildable area is only {plot_height} ft deep."
            )
        minimum_area += spec["min_width"] * spec["min_height"]
    if minimum_area > plot_width * plot_height:
        return False, (
            f"Rooms require at least {minimum_area} sq ft, "
            f"but the buildable area has only {plot_width * plot_height} sq ft."
        )
    return True, "Basic feasibility checks passed."


def calculate_buildable_area(plot_width, plot_height, setbacks):
    if type(plot_width) is not int or plot_width <= 0:
        raise ValueError("Plot width must be a positive integer.")
    if type(plot_height) is not int or plot_height <= 0:
        raise ValueError("Plot height must be a positive integer.")
    required = {"left", "right", "front", "back"}
    if not isinstance(setbacks, dict) or set(setbacks) != required:
        raise ValueError("Setbacks must contain exactly: left, right, front, and back.")
    for side, value in setbacks.items():
        if type(value) is not int or value < 0:
            raise ValueError(f"The {side} setback must be a non-negative integer.")
    width = plot_width - setbacks["left"] - setbacks["right"]
    depth = plot_height - setbacks["front"] - setbacks["back"]
    if width <= 0 or depth <= 0:
        raise ValueError("Setbacks leave no positive buildable area.")
    return {"width": width, "depth": depth, "offset_x": setbacks["left"], "offset_y": setbacks["front"]}


def _add_room_to_any_hallway(model, room, hallway_slots, W, L, tag):
    """Require a room to touch at least one active hallway segment."""
    choices = []
    for index, slot in enumerate(hallway_slots):
        choice = model.new_bool_var(f"{tag}_hallway_{index + 1}")
        add_adjacency(
            model, room, slot["vars"], HALLWAY_ROOM_WALL_MIN, W, L,
            f"{tag}_to_hallway_{index + 1}", enforce=choice,
        )
        model.add_implication(choice, slot["active"])
        choices.append(choice)
    model.add_bool_or(choices)


def _add_hallway_network_connectivity(model, hallway_slots, W, L):
    """Use a single-commodity flow to force all active hallway segments connected.

    Connectivity is formed only by hallway-to-hallway shared walls; room nodes
    cannot carry flow and therefore cannot join otherwise disconnected corridors.
    """
    count = len(hallway_slots)
    if count == 1:
        return

    edge_vars = {}
    flow = {}
    capacity = count - 1

    for i in range(count):
        for j in range(i + 1, count):
            edge = model.new_bool_var(f"hallway_edge_{i + 1}_{j + 1}")
            add_adjacency(
                model,
                hallway_slots[i]["vars"],
                hallway_slots[j]["vars"],
                HALLWAY_NETWORK_WALL_MIN,
                W,
                L,
                f"hallway_link_{i + 1}_{j + 1}",
                enforce=edge,
            )
            model.add_implication(edge, hallway_slots[i]["active"])
            model.add_implication(edge, hallway_slots[j]["active"])
            edge_vars[i, j] = edge

            flow[i, j] = model.new_int_var(0, capacity, f"hall_flow_{i}_{j}")
            flow[j, i] = model.new_int_var(0, capacity, f"hall_flow_{j}_{i}")
            model.add(flow[i, j] <= capacity * edge)
            model.add(flow[j, i] <= capacity * edge)

    # Root segment 0 supplies one unit to every other active segment.
    for node in range(count):
        incoming = [flow[other, node] for other in range(count) if other != node]
        outgoing = [flow[node, other] for other in range(count) if other != node]
        if node == 0:
            model.add(sum(outgoing) - sum(incoming) == sum(slot["active"] for slot in hallway_slots[1:]))
        else:
            model.add(sum(incoming) - sum(outgoing) == hallway_slots[node]["active"])


def _add_5x5_hallway_square_constraint(
    model, hallway_slots, W, L, square_x, square_y
):
    """
    Prevent the combined active hallway network from
    completely covering one specific 5x5 ft square.

    Coordinates and dimensions use integer feet.
    Active hallway segments must be non-overlapping.
    """

    if not hallway_slots or W < 5 or L < 5:
        return

    if not (0 <= square_x <= W - 5):
        raise ValueError("Invalid 5x5 square x-coordinate.")

    if not (0 <= square_y <= L - 5):
        raise ValueError("Invalid 5x5 square y-coordinate.")

    segment_areas = []

    for index, slot in enumerate(hallway_slots):

        x = slot["vars"]["x"]
        y = slot["vars"]["y"]
        w = slot["vars"]["w"]
        h = slot["vars"]["h"]
        active = slot["active"]

        prefix = f"hall_{index}_square_{square_x}_{square_y}"

        # Horizontal intersection.
        left = model.new_int_var(0, W, f"{prefix}_left")
        right = model.new_int_var(0, W, f"{prefix}_right")

        model.add_max_equality(left, [x, square_x])
        model.add_min_equality(right, [x + w, square_x + 5])

        raw_width = model.new_int_var(-W, W, f"{prefix}_raw_width")
        intersection_width = model.new_int_var(
            0, 5, f"{prefix}_width"
        )

        model.add(raw_width == right - left)
        model.add_max_equality(
            intersection_width, [raw_width, 0]
        )

        # Vertical intersection.
        bottom = model.new_int_var(0, L, f"{prefix}_bottom")
        top = model.new_int_var(0, L, f"{prefix}_top")

        model.add_max_equality(bottom, [y, square_y])
        model.add_min_equality(top, [y + h, square_y + 5])

        raw_height = model.new_int_var(-L, L, f"{prefix}_raw_height")
        intersection_height = model.new_int_var(
            0, 5, f"{prefix}_height"
        )

        model.add(raw_height == top - bottom)
        model.add_max_equality(
            intersection_height, [raw_height, 0]
        )

        # Calculate exact intersection area.
        intersection_area = model.new_int_var(
            0, 25, f"{prefix}_intersection_area"
        )

        model.add_multiplication_equality(
            intersection_area,
            [intersection_width, intersection_height],
        )

        # Count the area only if this hallway is active.
        active_area = model.new_int_var(
            0, 25, f"{prefix}_active_area"
        )

        model.add_multiplication_equality(
            active_area,
            [intersection_area, active],
        )

        segment_areas.append(active_area)

    # No complete 5x5 square: maximum covered area is 24 sq ft.
    model.add(sum(segment_areas) <= 24)


def _find_5x5_hallway_square(segments):
    """
    Find one complete 5x5 square inside the combined
    hallway network.

    Returns:
        (x, y) if a violation exists.
        None otherwise.
    """

    if not segments:
        return None

    min_x = min(segment["x"] for segment in segments)
    min_y = min(segment["y"] for segment in segments)

    max_x = max(
        segment["x"] + segment["w"] for segment in segments
    )
    max_y = max(
        segment["y"] + segment["h"] for segment in segments
    )

    for start_x in range(min_x, max_x - 4):
        for start_y in range(min_y, max_y - 4):

            square_is_covered = True

            for dx in range(5):
                for dy in range(5):

                    cell_x = start_x + dx + 0.5
                    cell_y = start_y + dy + 0.5

                    covered = any(
                        segment["x"] <= cell_x < segment["x"] + segment["w"]
                        and
                        segment["y"] <= cell_y < segment["y"] + segment["h"]
                        for segment in segments
                    )

                    if not covered:
                        square_is_covered = False
                        break

                if not square_is_covered:
                    break

            if square_is_covered:
                return start_x, start_y

    return None


def _solve_with_hallway_square_cuts(
    model,
    hallway_slots,
    W,
    L,
    time_limit_seconds,
    include_hallway=True,
):
    """
    Solve the CP-SAT model using iterative 5x5 hallway constraints.

    Returns:
        solver: CP-SAT solver instance
        status: Final solver status
        iterations: Number of solving attempts
    """

    solve_start = time.monotonic()

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 8

    status = cp_model.UNKNOWN
    iteration = 0

    while True:
        iteration += 1

        elapsed = time.monotonic() - solve_start
        remaining_time = float(time_limit_seconds) - elapsed

        if remaining_time <= 0:
            status = cp_model.UNKNOWN
            break

        solver.parameters.max_time_in_seconds = remaining_time

        print(f"\n5x5 constraint iteration: {iteration}")

        status = solver.solve(model)

        if status == cp_model.INFEASIBLE:
            break

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break

        candidate_segments = []

        if include_hallway:
            for slot in hallway_slots:
                if solver.value(slot["active"]):
                    x = solver.value(slot["vars"]["x"])
                    y = solver.value(slot["vars"]["y"])
                    w = solver.value(slot["vars"]["w"])
                    h = solver.value(slot["vars"]["h"])

                    candidate_segments.append({
                        "id": slot["id"],
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h,
                        "area": w * h,
                    })

        violating_square = _find_5x5_hallway_square(
            candidate_segments
        )

        if violating_square is None:
            print("Candidate passed the 5x5 hallway check.")
            break

        square_x, square_y = violating_square

        print(
            f"5x5 violation at ({square_x}, {square_y}). "
            "Adding a constraint and solving again."
        )

        _add_5x5_hallway_square_constraint(
            model,
            hallway_slots,
            W,
            L,
            square_x,
            square_y,
        )

    return solver, status, iteration


def solve_layout(
    plot_width=20,
    plot_height=12,
    room_specs=None,
    setbacks=None,
    include_hallway=False,
    layout_input=None,
    require_full_coverage=False,
    max_hallway_segments=HALLWAY_MAX_SEGMENTS,
    time_limit_seconds=10,
):
    if room_specs is None:
        room_specs = DEFAULT_ROOM_SPECS
    if setbacks is None:
        setbacks = {"left": 0, "right": 0, "front": 0, "back": 0}

    validate_inputs(plot_width, plot_height, room_specs)
    buildable = calculate_buildable_area(plot_width, plot_height, setbacks)
    W, L = buildable["width"], buildable["depth"]
    feasible, message = check_feasibility(W, L, room_specs)
    result_info = {
        "plot_width": plot_width,
        "plot_height": plot_height,
        "buildable_width": W,
        "buildable_depth": L,
        "buildable_area": W * L,
        "setbacks": setbacks,
        "buildable_offset_x": buildable["offset_x"],
        "buildable_offset_y": buildable["offset_y"],
    }
    if not feasible:
        return {**result_info, "status": "infeasible", "message": message, "rooms": None}

    if type(max_hallway_segments) is not int or max_hallway_segments < 1:
        raise ValueError("max_hallway_segments must be a positive integer.")
    if type(time_limit_seconds) not in (int, float) or time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be positive.")

    if include_hallway:
        if not isinstance(layout_input, dict) or not isinstance(layout_input.get("rooms"), list):
            raise ValueError("layout_input with a rooms list is required when include_hallway=True")
        input_names = {room.get("name") for room in layout_input["rooms"]}
        missing = set(room_specs) - input_names
        if missing:
            raise ValueError(f"Room specifications missing from layout_input: {sorted(missing)}")
        if "hallway_1" in room_specs or "hallway" in room_specs:
            raise ValueError("Room names 'hallway' and 'hallway_1' are reserved.")
        if not any(room.get("type") == "living" for room in layout_input["rooms"]):
            raise ValueError("At least one living room is required for entrance placement.")

    model = cp_model.CpModel()
    x_vars, y_vars, width_vars, height_vars = {}, {}, {}, {}
    x_intervals, y_intervals = [], []

    # Room variables and mandatory room intervals.
    for name, spec in room_specs.items():
        x = model.new_int_var(0, W, f"{name}_x")
        y = model.new_int_var(0, L, f"{name}_y")
        w = model.new_int_var(spec["min_width"], min(spec["max_width"], W), f"{name}_width")
        h = model.new_int_var(spec["min_height"], min(spec["max_height"], L), f"{name}_height")

        # Keep the current P1 room-dimension contract unchanged.

        model.add(x + w <= W)
        model.add(y + h <= L)
        x_end = model.new_int_var(0, W, f"{name}_x_end")
        y_end = model.new_int_var(0, L, f"{name}_y_end")
        model.add(x_end == x + w)
        model.add(y_end == y + h)
        x_intervals.append(model.new_interval_var(x, w, x_end, f"{name}_x_interval"))
        y_intervals.append(model.new_interval_var(y, h, y_end, f"{name}_y_interval"))

        x_vars[name], y_vars[name] = x, y
        width_vars[name], height_vars[name] = w, h

    hallway_slots = []
    if include_hallway:
        # Finite candidate upper bound: area-based, capped for MVP performance.
        area_bound = max(1, (W * L) // (HALLWAY_MIN_SHORT_SIDE ** 2))
        slot_count = min(max_hallway_segments, HALLWAY_MAX_SEGMENTS, area_bound)
        if slot_count < 1:
            raise ValueError("At least one hallway candidate slot is required.")

        for index in range(slot_count):
            segment_id = f"hallway_{index + 1}"
            active = model.new_bool_var(f"{segment_id}_active")
            x = model.new_int_var(0, W, f"{segment_id}_x")
            y = model.new_int_var(0, L, f"{segment_id}_y")
            w = model.new_int_var(1, W, f"{segment_id}_w")
            h = model.new_int_var(1, L, f"{segment_id}_h")
            x_end = model.new_int_var(0, W, f"{segment_id}_x_end")
            y_end = model.new_int_var(0, L, f"{segment_id}_y_end")
            # Keep candidate coordinates bounded even while inactive; adjacency
            # helper min/max expressions are created for every candidate pair.
            model.add(x + w <= W)
            model.add(y + h <= L)
            model.add(x_end == x + w).only_enforce_if(active)
            model.add(y_end == y + h).only_enforce_if(active)

            x_interval = model.new_optional_interval_var(x, w, x_end, active, f"{segment_id}_x_interval")
            y_interval = model.new_optional_interval_var(y, h, y_end, active, f"{segment_id}_y_interval")
            x_intervals.append(x_interval)
            y_intervals.append(y_interval)

            horizontal = model.new_bool_var(f"{segment_id}_horizontal")
            vertical = model.new_bool_var(f"{segment_id}_vertical")
            model.add(horizontal + vertical == active)
            model.add(h >= HALLWAY_MIN_SHORT_SIDE).only_enforce_if(horizontal)
            model.add(h <= HALLWAY_MAX_SHORT_SIDE).only_enforce_if(horizontal)
            model.add(w >= h).only_enforce_if(horizontal)
            model.add(w >= HALLWAY_MIN_SHORT_SIDE).only_enforce_if(vertical)
            model.add(w <= HALLWAY_MAX_SHORT_SIDE).only_enforce_if(vertical)
            model.add(h >= w).only_enforce_if(vertical)

            long_side = model.new_int_var(1, max(W, L), f"{segment_id}_long_side")
            model.add_max_equality(long_side, [w, h])
            counted_length = model.new_int_var(0, max(W, L), f"{segment_id}_counted_length")
            model.add(counted_length == long_side).only_enforce_if(active)
            model.add(counted_length == 0).only_enforce_if(active.Not())

            raw_area = model.new_int_var(1, W * L, f"{segment_id}_raw_area")
            model.add_multiplication_equality(raw_area, [w, h])
            counted_area = model.new_int_var(0, W * L, f"{segment_id}_counted_area")
            model.add(counted_area == raw_area).only_enforce_if(active)
            model.add(counted_area == 0).only_enforce_if(active.Not())

            hallway_slots.append({
                "id": segment_id,
                "active": active,
                "vars": {"x": x, "y": y, "w": w, "h": h},
                "long_side": counted_length,
                "area": counted_area,
            })

        # At least one segment; active slots form a prefix to remove symmetry.
        model.add(hallway_slots[0]["active"] == 1)
        for index in range(slot_count - 1):
            model.add(hallway_slots[index]["active"] >= hallway_slots[index + 1]["active"])
        model.add(sum(slot["long_side"] for slot in hallway_slots) >= HALLWAY_MIN_TOTAL_LENGTH)

        _add_hallway_network_connectivity(model, hallway_slots, W, L)

        # Room-to-hallway pairs are ORs across all candidate segments.
        room_variables = {
            name: {"x": x_vars[name], "y": y_vars[name], "w": width_vars[name], "h": height_vars[name]}
            for name in room_specs
        }
        for pair_index, (a, b) in enumerate(required_pairs(layout_input)):
            if a not in room_variables:
                raise ValueError(f"Invalid adjacency pair: unknown room '{a}'.")
            if b in ("hallway", "hallway_1"):
                _add_room_to_any_hallway(model, room_variables[a], hallway_slots, W, L, f"room_{a}_{pair_index}")
            else:
                if b not in room_variables:
                    raise ValueError(f"Invalid adjacency pair: unknown room '{b}'.")
                add_adjacency(model, room_variables[a], room_variables[b], 3, W, L, f"room_adj_{pair_index}")

        # The first living room touches the selected entrance boundary.
        living_name = next(room["name"] for room in layout_input["rooms"] if room["type"] == "living")
        living = room_variables[living_name]
        entrance = layout_input.get("entrance", "S")
        north = layout_input.get("north", "up")
        if north not in ENTRANCE_EDGE or entrance not in ENTRANCE_EDGE[north]:
            raise ValueError(f"Invalid entrance/north combination: entrance={entrance}, north={north}.")
        edge = ENTRANCE_EDGE[north][entrance]
        if edge == "bottom":
            model.add(living["y"] == 0)
        elif edge == "top":
            model.add(living["y"] + living["h"] == L)
        elif edge == "left":
            model.add(living["x"] == 0)
        else:
            model.add(living["x"] + living["w"] == W)

    # Area accounting. Optional hallway segments contribute zero when inactive.
    buildable_area_total = W * L
    room_area_vars = {}
    for name in room_specs:
        area_var = model.new_int_var(0, buildable_area_total, f"{name}_area")
        model.add_multiplication_equality(area_var, [width_vars[name], height_vars[name]])
        room_area_vars[name] = area_var

    hallway_area_vars = [slot["area"] for slot in hallway_slots]
    total_occupied_area = sum(room_area_vars.values()) + sum(hallway_area_vars)

    if include_hallway and require_full_coverage:
        model.add(total_occupied_area == buildable_area_total)

    model.add_no_overlap_2d(x_intervals, y_intervals)

    if include_hallway:
        # Coverage is primary; for equal coverage prefer less hallway area and
        # then fewer segments. This naturally returns full coverage when feasible.
        secondary_scale = len(hallway_slots) + 1
        coverage_weight = buildable_area_total * secondary_scale + len(hallway_slots) + 1
        model.maximize(
            total_occupied_area * coverage_weight
            - sum(hallway_area_vars) * secondary_scale
            - sum(slot["active"] for slot in hallway_slots)
        )

    solver, status, iterations = _solve_with_hallway_square_cuts(
        model=model,
        hallway_slots=hallway_slots,
        W=W,
        L=L,
        time_limit_seconds=time_limit_seconds,
        include_hallway=include_hallway,
    )

    if status == cp_model.INFEASIBLE:
        return {**result_info, "status": "infeasible", "message": "No arrangement satisfies all geometry and connectivity constraints.", "rooms": None}
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {**result_info, "status": "unknown", "message": "The solver did not find a solution within the time limit.", "rooms": None}

    rooms = {}
    for name in room_specs:
        x, y = solver.value(x_vars[name]), solver.value(y_vars[name])
        w, h = solver.value(width_vars[name]), solver.value(height_vars[name])
        rooms[name] = {"x": x, "y": y, "width": w, "height": h, "w": w, "h": h, "area": w * h}

    result = {
        **result_info,
        "status": "success",
        "message": "A valid layout was found.",
        "rooms": rooms,
        "solver_status": solver.status_name(status),
    }
    if include_hallway:
        segments = []
        for slot in hallway_slots:
            if solver.value(slot["active"]):
                x = solver.value(slot["vars"]["x"])
                y = solver.value(slot["vars"]["y"])
                w = solver.value(slot["vars"]["w"])
                h = solver.value(slot["vars"]["h"])
                segments.append({"id": slot["id"], "x": x, "y": y, "w": w, "h": h, "area": w * h})
        result["hallway_segments"] = segments
        result["hallway_count"] = len(segments)
        result["coverage_optimality_proven"] = status == cp_model.OPTIMAL
        if len(segments) == 1:
            result["hallway"] = segments[0]  # backward compatibility for existing callers
        occupied = sum(room["area"] for room in rooms.values()) + sum(segment["area"] for segment in segments)
        result["occupied_area"] = occupied
        result["unused_area"] = buildable_area_total - occupied
        result["coverage_percent"] = round(100 * occupied / buildable_area_total, 2)
        result["message"] = (
            "A valid full-coverage layout was found."
            if occupied == buildable_area_total
            else f"A valid partial-coverage layout was found ({result['coverage_percent']}% coverage)."
        )
    return result


def read_positive_integer(prompt):
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
    print("=== Floor Plan Solver ===")
    width = read_positive_integer("Enter plot width (ft): ")
    height = read_positive_integer("Enter plot height (ft): ")
    result = solve_layout(plot_width=width, plot_height=height)
    print(result)
