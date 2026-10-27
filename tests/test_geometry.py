import pytest

from floorplan.geometry import solve_two_rooms, validate_inputs


def test_solver_finds_a_layout():
    result = solve_two_rooms()

    assert result is not None


def test_rooms_stay_inside_buildable_area():
    result = solve_two_rooms()

    assert result is not None

    plot_width = result["plot_width"]
    plot_height = result["plot_height"]

    for room in result["rooms"].values():
        assert room["x"] >= 0
        assert room["y"] >= 0
        assert room["x"] + room["width"] <= plot_width
        assert room["y"] + room["height"] <= plot_height


def test_rooms_do_not_overlap():
    result = solve_two_rooms()

    assert result is not None

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
    result = solve_two_rooms()

    assert result is not None

    for room in result["rooms"].values():
        assert room["area"] == room["width"] * room["height"]


def test_rooms_respect_dimension_limits():
    result = solve_two_rooms()

    assert result is not None

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
    result = solve_two_rooms(plot_width=24, plot_height=14)

    assert result is not None
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

    result = solve_two_rooms(
        plot_width=10,
        plot_height=10,
        room_specs=custom_rooms,
    )

    assert result is not None
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
