
import pytest

from floorplan.geometry import solve_layout
from validate_all import (
    adapt_solver_result,
    validate_all,
    validate_solver_result,
)


# --------------------------------------------------
# Shared test input
# --------------------------------------------------

LAYOUT_INPUT = {
    "plot": [16, 12],
    "setbacks": {
        "left": 0,
        "right": 0,
        "front": 0,
        "back": 0,
    },
    "entrance": "S",
    "north": "up",
    "rooms": [
        {
            "name": "living",
            "type": "living",
        }
    ],
}

ROOM_SPECS = {
    "living": {
        "min_width": 12,
        "max_width": 12,
        "min_height": 12,
        "max_height": 12,
    }
}


# --------------------------------------------------
# Helper: generate a valid solver result
# --------------------------------------------------

@pytest.fixture
def solver_result():
    result = solve_layout(
        plot_width=16,
        plot_height=12,
        room_specs=ROOM_SPECS,
        setbacks=LAYOUT_INPUT["setbacks"],
        include_hallway=True,
        layout_input=LAYOUT_INPUT,
        require_full_coverage=True,
    )

    assert result["status"] == "success", result

    return result


# --------------------------------------------------
# Test 1: Solver generates a layout
# --------------------------------------------------

def test_solver_generates_successful_layout(solver_result):
    assert solver_result["status"] == "success"
    assert solver_result["rooms"] is not None
    assert solver_result["hallway"] is not None


# --------------------------------------------------
# Test 2: Adapter converts the solver output
# --------------------------------------------------

def test_adapter_converts_solver_output(solver_result):
    layout = adapt_solver_result(solver_result)

    assert isinstance(layout["rooms"], list)

    assert layout["rooms"][0]["name"] == "living"

    assert "w" in layout["rooms"][0]
    assert "h" in layout["rooms"][0]

    assert layout["hallway"]["id"] == "hallway_1"


# --------------------------------------------------
# Test 3: Valid generated layout passes P4
# --------------------------------------------------

def test_valid_solver_layout_passes_p4(solver_result):
    problems = validate_solver_result(
        LAYOUT_INPUT,
        solver_result,
    )

    assert problems == []


# --------------------------------------------------
# Test 4: P4 detects overlapping rooms
# --------------------------------------------------

def test_p4_detects_overlapping_rooms():
    overlapping_layout = {
        "rooms": [
            {
                "name": "living",
                "x": 0,
                "y": 0,
                "w": 12,
                "h": 12,
            }
        ],
        "hallway": {
            "id": "hallway_1",
            "x": 11,
            "y": 0,
            "w": 4,
            "h": 12,
        },
    }

    problems = validate_all(
        LAYOUT_INPUT,
        overlapping_layout,
    )

    assert any(
        problem["code"] == "H3"
        for problem in problems
    )


# --------------------------------------------------
# Test 5: P4 detects uncovered area
# --------------------------------------------------

def test_p4_detects_uncovered_area():
    layout_with_gap = {
        "rooms": [
            {
                "name": "living",
                "x": 0,
                "y": 0,
                "w": 12,
                "h": 12,
            }
        ],
        "hallway": {
            "id": "hallway_1",
            "x": 13,
            "y": 0,
            "w": 3,
            "h": 12,
        },
    }

    problems = validate_all(
        LAYOUT_INPUT,
        layout_with_gap,
    )

    assert any(
        problem["code"] == "H4"
        for problem in problems
    )


# --------------------------------------------------
# Test 6: Unsuccessful solver results are rejected
# --------------------------------------------------

def test_adapter_rejects_unsuccessful_solver_result():
    unsuccessful_result = {
        "status": "infeasible",
        "message": "No feasible layout found.",
        "rooms": None,
    }

    with pytest.raises(ValueError):
        adapt_solver_result(unsuccessful_result)
