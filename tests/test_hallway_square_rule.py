
from floorplan.connections_check import check_no_5x5_hallway_square

from ortools.sat.python import cp_model

from floorplan.geometry import (
    _add_5x5_hallway_square_constraint,
    _find_5x5_hallway_square,
    _solve_with_hallway_square_cuts,
)

def test_targeted_5x5_constraint_prevents_square():
    model = cp_model.CpModel()

    # Two hallway segments initially form a 5x5 square.
    hallway_slots = []

    # Segment 1: 5x3 at (0, 0).
    # Segment 2: 5x2 at (0, 3).
    segment_data = [
        (0, 0, 5, 3),
        (0, 3, 5, 2),
    ]

    for index, (x_value, y_value, w_value, h_value) in enumerate(segment_data):
        x = model.new_int_var(x_value, x_value, f"x_{index}")
        y = model.new_int_var(y_value, y_value, f"y_{index}")
        w = model.new_int_var(w_value, w_value, f"w_{index}")
        h = model.new_int_var(h_value, h_value, f"h_{index}")

        active = model.new_bool_var(f"active_{index}")
        model.add(active == 1)

        hallway_slots.append({
            "id": f"hallway_{index + 1}",
            "active": active,
            "vars": {"x": x, "y": y, "w": w, "h": h},
        })

    # Confirm that the initial hallway arrangement violates HW3.
    initial_segments = [
        {"x": x, "y": y, "w": w, "h": h}
        for x, y, w, h in segment_data
    ]

    assert _find_5x5_hallway_square(initial_segments) == (0, 0)

    # Add the targeted constraint for the violating square.
    _add_5x5_hallway_square_constraint(
        model,
        hallway_slots,
        W=10,
        L=10,
        square_x=0,
        square_y=0,
    )

    solver = cp_model.CpSolver()
    status = solver.solve(model)

    # The fixed hallway segments cannot change, so the model
    # must now be infeasible.
    assert status == cp_model.INFEASIBLE


def make_layout(halls):
    return {
        "rooms": [],
        "hallway_segments": halls
    }

def test_rejects_10_by_7_hallway():
    layout = make_layout([
        {"name": "hallway_1", "x": 8, "y": 21, "w": 10, "h": 3},
        {"name": "hallway_2", "x": 8, "y": 17, "w": 10, "h": 4},
    ])

    assert check_no_5x5_hallway_square(layout)


def test_accepts_4_by_12_corridor():
    layout = make_layout([
        {"name": "hallway_1", "x": 0, "y": 0, "w": 12, "h": 4},
    ])

    assert check_no_5x5_hallway_square(layout) == []


def test_rejects_square_created_by_multiple_segments():
    layout = make_layout([
        {"name": "hallway_1", "x": 0, "y": 0, "w": 5, "h": 3},
        {"name": "hallway_2", "x": 0, "y": 3, "w": 5, "h": 2},
    ])

    assert check_no_5x5_hallway_square(layout)


def test_accepts_l_shaped_corridor():
    layout = make_layout([
        {"name": "hallway_1", "x": 0, "y": 0, "w": 12, "h": 4},
        {"name": "hallway_2", "x": 8, "y": 4, "w": 4, "h": 8},
    ])

    assert check_no_5x5_hallway_square(layout) == []


def test_accepts_t_shaped_corridor():
    layout = make_layout([
        {"name": "hallway_1", "x": 0, "y": 0, "w": 12, "h": 4},
        {"name": "hallway_2", "x": 4, "y": 4, "w": 4, "h": 8},
    ])

    assert check_no_5x5_hallway_square(layout) == []


def test_no_hallways():
    assert check_no_5x5_hallway_square({"rooms": []}) == []


def test_iterative_solver_rejects_square_and_finds_alternative():
    model = cp_model.CpModel()

    # Both hallway segments are active and have fixed dimensions.
    # The second segment can occupy either:
    #   y = 3: creates a 5x5 square with the first segment.
    #   y = 5: leaves a gap and avoids the 5x5 square.

    invalid_layout = model.new_bool_var("invalid_layout")

    hallway_slots = []

    # First segment: 5x3 at (0, 0).
    x1 = model.new_int_var(0, 0, "x1")
    y1 = model.new_int_var(0, 0, "y1")
    w1 = model.new_int_var(5, 5, "w1")
    h1 = model.new_int_var(3, 3, "h1")
    active1 = model.new_bool_var("active1")
    model.add(active1 == 1)

    hallway_slots.append({
        "id": "hallway_1",
        "active": active1,
        "vars": {"x": x1, "y": y1, "w": w1, "h": h1},
    })

    # Second segment: 5x2.
    x2 = model.new_int_var(0, 0, "x2")
    y2 = model.new_int_var(3, 5, "y2")
    w2 = model.new_int_var(5, 5, "w2")
    h2 = model.new_int_var(2, 2, "h2")
    active2 = model.new_bool_var("active2")
    model.add(active2 == 1)

    # invalid_layout = 1 means y2 = 3.
    # invalid_layout = 0 means y2 = 5.
    model.add(y2 == 3).only_enforce_if(invalid_layout)
    model.add(y2 == 5).only_enforce_if(invalid_layout.Not())

    hallway_slots.append({
        "id": "hallway_2",
        "active": active2,
        "vars": {"x": x2, "y": y2, "w": w2, "h": h2},
    })

    # Initially prefer the invalid arrangement.
    model.maximize(invalid_layout)

    solver, status, iterations = _solve_with_hallway_square_cuts(
        model=model,
        hallway_slots=hallway_slots,
        W=10,
        L=10,
        time_limit_seconds=10,
        include_hallway=True,
    )

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    # First solve should be rejected; second should be accepted.
    assert iterations == 2

    final_segments = [
        {
            "x": solver.value(slot["vars"]["x"]),
            "y": solver.value(slot["vars"]["y"]),
            "w": solver.value(slot["vars"]["w"]),
            "h": solver.value(slot["vars"]["h"]),
        }
        for slot in hallway_slots
        if solver.value(slot["active"])
    ]

    assert solver.value(invalid_layout) == 0
    assert _find_5x5_hallway_square(final_segments) is None
