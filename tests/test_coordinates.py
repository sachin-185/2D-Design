
import pytest

from floorplan.coordinates import (
    plot_origin,
    to_plot_coordinates,
    to_buildable_coordinates,
)


SETBACKS = {
    "left": 3,
    "right": 2,
    "front": 4,
    "back": 3,
}


def test_plot_origin():
    assert plot_origin(SETBACKS) == (3, 4)


def test_plot_origin_missing_setbacks():
    assert plot_origin(None) == (0, 0)


def test_plot_origin_missing_sides():
    assert plot_origin({"left": 3}) == (3, 0)


def test_plot_origin_rejects_explicit_none():
    with pytest.raises(ValueError):
        plot_origin({"left": None})


def test_buildable_to_plot_coordinates():
    layout = {
        "rooms": [
            {"name": "Living", "x": 0, "y": 0, "w": 12, "h": 12},
            {"name": "Bedroom", "x": 25, "y": 13, "w": 10, "h": 10},
        ]
    }

    result = to_plot_coordinates(layout, SETBACKS)

    assert result["rooms"][0]["x"] == 3
    assert result["rooms"][0]["y"] == 4

    assert result["rooms"][1]["x"] == 28
    assert result["rooms"][1]["y"] == 17


def test_plot_to_buildable_coordinates():
    layout = {
        "rooms": [
            {"name": "Living", "x": 3, "y": 4, "w": 12, "h": 12}
        ]
    }

    result = to_buildable_coordinates(layout, SETBACKS)

    assert result["rooms"][0]["x"] == 0
    assert result["rooms"][0]["y"] == 0


def test_fractional_coordinates_are_preserved():
    layout = {
        "doors": [
            {"x": 12, "y": 7.5, "width": 3}
        ]
    }

    result = to_plot_coordinates(layout, SETBACKS)

    assert result["doors"][0]["x"] == 15
    assert result["doors"][0]["y"] == 11.5


def test_conversion_does_not_modify_original():
    layout = {
        "rooms": [
            {"name": "Living", "x": 0, "y": 0, "w": 12, "h": 12}
        ]
    }

    original = {
        "rooms": [
            {"name": "Living", "x": 0, "y": 0, "w": 12, "h": 12}
        ]
    }

    to_plot_coordinates(layout, SETBACKS)

    assert layout == original


def test_round_trip_conversion():
    layout = {
        "rooms": [
            {"name": "Living", "x": 5, "y": 3, "w": 12, "h": 12}
        ]
    }

    plot_layout = to_plot_coordinates(layout, SETBACKS)
    result = to_buildable_coordinates(plot_layout, SETBACKS)

    assert result == layout


def test_all_positioned_objects_are_converted():
    layout = {
        "rooms": [
            {"name": "Living", "x": 0, "y": 0, "w": 12, "h": 12}
        ],
        "hallway_segments": [
            {"id": "hallway_1", "x": 12, "y": 0, "w": 12, "h": 3}
        ],
        "doors": [
            {"x": 12, "y": 7.5, "width": 3}
        ],
        "windows": [
            {"room": "Living", "wall": "south", "x": 4.3}
        ],
    }

    result = to_plot_coordinates(layout, SETBACKS)

    assert result["rooms"][0]["x"] == 3
    assert result["rooms"][0]["y"] == 4

    assert result["hallway_segments"][0]["x"] == 15
    assert result["hallway_segments"][0]["y"] == 4

    assert result["doors"][0]["x"] == 15
    assert result["doors"][0]["y"] == 11.5

    assert result["windows"][0]["x"] == 7.3


def test_window_optional_y_is_converted_when_present():
    layout = {
        "windows": [
            {"room": "Living", "x": 4, "y": 0}
        ]
    }

    result = to_plot_coordinates(layout, SETBACKS)

    assert result["windows"][0]["x"] == 7
    assert result["windows"][0]["y"] == 4


def test_window_none_y_remains_none():
    layout = {
        "windows": [
            {"room": "Living", "x": 4, "y": None}
        ]
    }

    result = to_plot_coordinates(layout, SETBACKS)

    assert result["windows"][0]["y"] is None


def test_legacy_hallway_is_converted():
    layout = {
        "rooms": [],
        "hallway": {
            "x": 12,
            "y": 0,
            "w": 12,
            "h": 3
        }
    }

    result = to_plot_coordinates(layout, SETBACKS)

    assert result["hallway"]["x"] == 15
    assert result["hallway"]["y"] == 4


def test_dimensions_and_metadata_are_unchanged():
    layout = {
        "rooms": [
            {
                "name": "Living",
                "type": "living",
                "x": 0,
                "y": 0,
                "w": 12,
                "h": 12,
                "score": 95,
                "custom_metadata": "test"
            }
        ]
    }

    result = to_plot_coordinates(layout, SETBACKS)

    room = result["rooms"][0]

    assert room["w"] == 12
    assert room["h"] == 12
    assert room["score"] == 95
    assert room["custom_metadata"] == "test"


def test_empty_lists_remain_empty():
    layout = {
        "rooms": [],
        "hallway_segments": [],
        "doors": [],
        "windows": []
    }

    result = to_plot_coordinates(layout, SETBACKS)

    assert result == layout


def test_missing_lists_remain_missing():
    layout = {"rooms": []}

    result = to_plot_coordinates(layout, SETBACKS)

    assert "doors" not in result
    assert "windows" not in result
    assert "hallway_segments" not in result


def test_raw_solver_rooms_dictionary_is_rejected():
    layout = {
        "rooms": {
            "Living": {"x": 0, "y": 0, "w": 12, "h": 12}
        }
    }

    with pytest.raises(ValueError, match="rooms.*list"):
        to_plot_coordinates(layout, SETBACKS)


def test_missing_room_coordinate_is_rejected():
    layout = {
        "rooms": [
            {"name": "Living", "x": 0, "w": 12, "h": 12}
        ]
    }

    with pytest.raises(ValueError, match="room\\[0\\].*y"):
        to_plot_coordinates(layout, SETBACKS)


def test_boolean_coordinate_is_rejected():
    layout = {
        "rooms": [
            {"name": "Living", "x": True, "y": 0, "w": 12, "h": 12}
        ]
    }

    with pytest.raises(ValueError):
        to_plot_coordinates(layout, SETBACKS)

def test_fractional_setback_is_rejected():
    with pytest.raises(ValueError, match="non-negative integer"):
        plot_origin({"left": 2.5})


def test_negative_setback_is_rejected():
    with pytest.raises(ValueError, match="non-negative integer"):
        plot_origin({"front": -2})