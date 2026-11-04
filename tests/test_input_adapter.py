
import pytest

from floorplan.input_adapter import (
    build_room_specs,
    build_solver_arguments,
)


# Temporary test fixture only.
# These values are not confirmed production configuration.
TEST_ROOM_SIZE_TABLE = {
    "living": ([12, 12], [20, 20]),
    "kitchen": ([8, 8], [12, 12]),
    "bedroom": ([10, 10], [16, 16]),
    "bathroom": ([5, 7], [8, 10]),
}


@pytest.fixture
def sample_input():
    return {
        "plot": [30, 40],
        "setbacks": {
            "front": 5,
            "back": 3,
            "left": 3,
            "right": 3,
        },
        "entrance": "S",
        "north": "up",
        "rooms": [
            {
                "name": "living",
                "type": "living",
            },
            {
                "name": "bedroom1",
                "type": "bedroom",
                "zone": "NW",
                "zone_mode": "must",
            },
            {
                "name": "kitchen",
                "type": "kitchen",
            },
            {
                "name": "bathroom",
                "type": "bathroom",
            },
        ],
    }


def test_build_room_specs(sample_input):
    specs = build_room_specs(
        sample_input,
        TEST_ROOM_SIZE_TABLE
    )

    assert len(specs) == 4

    assert specs["living"]["min_width"] == 12
    assert specs["living"]["max_width"] == 20

    assert specs["bedroom1"]["min_height"] == 10
    assert specs["bedroom1"]["max_height"] == 16


def test_custom_dimensions_override_table(sample_input):
    sample_input["rooms"][0]["min"] = [14, 13]
    sample_input["rooms"][0]["max"] = [18, 19]

    specs = build_room_specs(
        sample_input,
        TEST_ROOM_SIZE_TABLE
    )

    assert specs["living"]["min_width"] == 14
    assert specs["living"]["min_height"] == 13
    assert specs["living"]["max_width"] == 18
    assert specs["living"]["max_height"] == 19


def test_build_solver_arguments(sample_input):
    args = build_solver_arguments(
        sample_input,
        TEST_ROOM_SIZE_TABLE
    )

    assert args["plot_width"] == 30
    assert args["plot_height"] == 40

    assert args["setbacks"]["front"] == 5
    assert args["setbacks"]["left"] == 3

    assert args["include_hallway"] is True

    assert args["layout_input"]["entrance"] == "S"
    assert args["layout_input"]["north"] == "up"

    assert len(args["layout_input"]["rooms"]) == 4


def test_missing_setbacks_default_to_zero(sample_input):
    sample_input.pop("setbacks")

    args = build_solver_arguments(
        sample_input,
        TEST_ROOM_SIZE_TABLE
    )

    assert args["setbacks"] == {
        "left": 0,
        "right": 0,
        "front": 0,
        "back": 0,
    }


def test_unknown_room_type_raises_error(sample_input):
    sample_input["rooms"][0]["type"] = "unknown"

    with pytest.raises(ValueError):
        build_room_specs(
            sample_input,
            TEST_ROOM_SIZE_TABLE
        )


def test_invalid_dimension_bounds_raise_error(sample_input):
    sample_input["rooms"][0]["min"] = [21, 12]
    sample_input["rooms"][0]["max"] = [20, 20]

    with pytest.raises(ValueError):
        build_room_specs(
            sample_input,
            TEST_ROOM_SIZE_TABLE
        )


def test_attached_to_is_preserved_in_solver_arguments(sample_input):
    # Attach the bathroom to bedroom1.
    sample_input["rooms"][3]["attached_to"] = "bedroom1"

    args = build_solver_arguments(
        sample_input,
        TEST_ROOM_SIZE_TABLE
    )

    bathroom = next(
        room
        for room in args["layout_input"]["rooms"]
        if room["name"] == "bathroom"
    )

    assert bathroom["attached_to"] == "bedroom1"
