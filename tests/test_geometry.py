import pytest

from floorplan.geometry import (
    solve_layout,
    validate_inputs,
    check_feasibility,
    calculate_buildable_area,
)

def test_solver_finds_a_layout():
    result = solve_layout()

    assert result["status"] == "success"

def test_rooms_stay_inside_buildable_area():
    result = solve_layout()

    assert result["status"] == "success"

    plot_width = result["plot_width"]
    plot_height = result["plot_height"]

    for room in result["rooms"].values():
        assert room["x"] >= 0
        assert room["y"] >= 0
        assert room["x"] + room["width"] <= plot_width
        assert room["y"] + room["height"] <= plot_height


def test_rooms_do_not_overlap():
    result = solve_layout()

    assert result["status"] == "success"

    rooms = list(result["rooms"].values())

    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            a = rooms[i]
            b = rooms[j]

            separated = (
                a["x"] + a["width"] <= b["x"]
                or b["x"] + b["width"] <= a["x"]
                or a["y"] + a["height"] <= b["y"]
                or b["y"] + b["height"] <= a["y"]
            )

            assert separated, "Two rooms overlap"


def test_room_areas_are_calculated_correctly():
    result = solve_layout()

    assert result["status"] == "success"

    for room in result["rooms"].values():
        assert room["area"] == room["width"] * room["height"]


def test_rooms_respect_dimension_limits():
    result = solve_layout()

    assert result["status"] == "success"

    dimension_limits = {
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

    for name, room in result["rooms"].items():
        limits = dimension_limits[name]

        assert limits["min_width"] <= room["width"] <= limits["max_width"]
        assert limits["min_height"] <= room["height"] <= limits["max_height"]


def test_solver_accepts_custom_plot_dimensions():
    result = solve_layout(plot_width=24, plot_height=14)

    assert result["status"] == "success"
    assert result["plot_width"] == 24
    assert result["plot_height"] == 14

    for room in result["rooms"].values():
        assert room["x"] + room["width"] <= 24
        assert room["y"] + room["height"] <= 14


def test_solver_accepts_custom_room_specs():
    custom_rooms = {
        "Kitchen": {
            "min_width": 5,
            "max_width": 8,
            "min_height": 6,
            "max_height": 9,
        }
    }

    result = solve_layout(
        plot_width=10,
        plot_height=10,
        room_specs=custom_rooms,
    )

    assert result["status"] == "success"
    assert set(result["rooms"].keys()) == {"Kitchen"}

    kitchen = result["rooms"]["Kitchen"]

    assert 5 <= kitchen["width"] <= 8
    assert 6 <= kitchen["height"] <= 9
    assert kitchen["x"] + kitchen["width"] <= 10
    assert kitchen["y"] + kitchen["height"] <= 10
    

def test_rejects_zero_plot_width():
    with pytest.raises(ValueError, match="Plot width"):
        validate_inputs(0, 12, {
            "Room A": {
                "min_width": 8,
                "max_width": 12,
                "min_height": 6,
                "max_height": 10,
            }
        })


def test_rejects_negative_room_dimensions():
    with pytest.raises(ValueError, match="positive integer"):
        validate_inputs(20, 12, {
            "Room A": {
                "min_width": -1,
                "max_width": 12,
                "min_height": 6,
                "max_height": 10,
            }
        })


def test_rejects_minimum_greater_than_maximum():
    with pytest.raises(ValueError, match="minimum width"):
        validate_inputs(20, 12, {
            "Room A": {
                "min_width": 12,
                "max_width": 8,
                "min_height": 6,
                "max_height": 10,
            }
        })


def test_feasibility_rejects_room_wider_than_plot():
    rooms = {
        "Bedroom": {
            "min_width": 15,
            "max_width": 18,
            "min_height": 8,
            "max_height": 10,
        }
    }

    feasible, message = check_feasibility(10, 20, rooms)

    assert feasible is False
    assert "minimum width" in message


def test_feasibility_accepts_basic_valid_example():
    rooms = {
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

    feasible, message = check_feasibility(20, 12, rooms)

    assert feasible is True
    assert message == "Basic feasibility checks passed."


def test_successful_result_has_status_and_message():
    result = solve_layout()

    assert result["status"] == "success"
    assert result["message"] == "A valid layout was found."
    assert result["rooms"] is not None


def test_infeasible_request_returns_explanation():
    impossible_rooms = {
        "Bedroom": {
            "min_width": 15,
            "max_width": 18,
            "min_height": 8,
            "max_height": 10,
        }
    }

    result = solve_layout(
        plot_width=10,
        plot_height=20,
        room_specs=impossible_rooms,
    )

    assert result["status"] == "infeasible"
    assert "minimum width" in result["message"]
    assert result["rooms"] is None


def test_calculates_buildable_area_after_setbacks():
    setbacks = {
        "left": 3,
        "right": 3,
        "front": 5,
        "back": 3,
    }

    result = calculate_buildable_area(30, 40, setbacks)

    assert result["width"] == 24
    assert result["depth"] == 32
    assert result["offset_x"] == 3
    assert result["offset_y"] == 5


def test_rejects_setbacks_that_leave_no_buildable_area():
    setbacks = {
        "left": 10,
        "right": 10,
        "front": 2,
        "back": 2,
    }

    with pytest.raises(ValueError, match="no positive buildable area"):
        calculate_buildable_area(20, 30, setbacks)


def test_solver_places_rooms_inside_buildable_area():
    setbacks = {
        "left": 3,
        "right": 3,
        "front": 5,
        "back": 3,
    }

    result = solve_layout(
        plot_width=30,
        plot_height=40,
        setbacks=setbacks,
    )

    assert result["status"] == "success"
    assert result["buildable_width"] == 24
    assert result["buildable_depth"] == 32

    for room in result["rooms"].values():
        assert room["x"] >= 0
        assert room["y"] >= 0
        assert room["x"] + room["width"] <= 24
        assert room["y"] + room["height"] <= 32

def test_rejects_missing_setback_key():
    setbacks = {
        "left": 3,
        "right": 3,
        "front": 5,
    }

    with pytest.raises(ValueError, match="exactly"):
        solve_layout(setbacks=setbacks)


def test_rejects_negative_setback():
    setbacks = {
        "left": -1,
        "right": 3,
        "front": 5,
        "back": 3,
    }

    with pytest.raises(ValueError, match="non-negative integer"):
        solve_layout(setbacks=setbacks)


def test_rejects_non_integer_setback():
    setbacks = {
        "left": 3.5,
        "right": 3,
        "front": 5,
        "back": 3,
    }

    with pytest.raises(ValueError, match="non-negative integer"):
        solve_layout(setbacks=setbacks)

def test_room_coordinates_can_be_translated_to_original_plot():
    setbacks = {
        "left": 3,
        "right": 3,
        "front": 5,
        "back": 3,
    }

    result = solve_layout(
        plot_width=30,
        plot_height=40,
        setbacks=setbacks,
    )

    assert result["status"] == "success"

    for room in result["rooms"].values():
        original_x = room["x"] + result["buildable_offset_x"]
        original_y = room["y"] + result["buildable_offset_y"]

        assert original_x >= 3
        assert original_y >= 5
        assert original_x + room["width"] <= 30 - 3
        assert original_y + room["height"] <= 40 - 3


def test_solver_rejects_missing_setback_key():
    setbacks = {
        "left": 3,
        "right": 3,
        "front": 5,
    }

    with pytest.raises(ValueError, match="exactly"):
        solve_layout(setbacks=setbacks)


def test_solver_rejects_negative_setback():
    setbacks = {
        "left": -1,
        "right": 3,
        "front": 5,
        "back": 3,
    }

    with pytest.raises(ValueError, match="non-negative integer"):
        solve_layout(setbacks=setbacks)


def test_solver_rejects_non_integer_setback():
    setbacks = {
        "left": 3.5,
        "right": 3,
        "front": 5,
        "back": 3,
    }

    with pytest.raises(ValueError, match="non-negative integer"):
        solve_layout(setbacks=setbacks)


def test_rooms_respect_setbacks_in_original_plot():
    setbacks = {
        "left": 3,
        "right": 3,
        "front": 5,
        "back": 3,
    }

    result = solve_layout(
        plot_width=30,
        plot_height=40,
        setbacks=setbacks,
    )

    assert result["status"] == "success"

    # Confirm that the buildable area begins at the expected offsets.
    assert result["buildable_offset_x"] == 3
    assert result["buildable_offset_y"] == 5

    for room in result["rooms"].values():
        # Convert buildable-area coordinates to original-plot coordinates.
        original_x = room["x"] + result["buildable_offset_x"]
        original_y = room["y"] + result["buildable_offset_y"]

        # The room must remain within all four setback boundaries.
        assert original_x >= 3
        assert original_y >= 5
        assert original_x + room["width"] <= 30 - 3
        assert original_y + room["height"] <= 40 - 3

def test_room_can_exactly_fit_buildable_area():
    room_specs = {
        "Small Room": {
            "min_width": 8,
            "max_width": 8,
            "min_height": 6,
            "max_height": 6,
        }
    }

    result = solve_layout(
        plot_width=8,
        plot_height=6,
        room_specs=room_specs,
    )

    assert result["status"] == "success"

    room = result["rooms"]["Small Room"]
    assert room["x"] == 0
    assert room["y"] == 0
    assert room["width"] == 8
    assert room["height"] == 6

def test_solver_rejects_room_that_cannot_fit_after_setbacks():
    room_specs = {
        "Bedroom": {
            "min_width": 8,
            "max_width": 10,
            "min_height": 6,
            "max_height": 8,
        }
    }

    setbacks = {
        "left": 2,
        "right": 2,
        "front": 1,
        "back": 1,
    }

    result = solve_layout(
        plot_width=11,
        plot_height=10,
        room_specs=room_specs,
        setbacks=setbacks,
    )

    assert result["status"] == "infeasible"
    assert result["rooms"] is None