
from floorplan.geometry import solve_two_rooms


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
