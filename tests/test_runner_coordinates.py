
from floorplan.schema import FloorPlanInput, ErrorResponse
from floorplan.runner import execute_pipeline
from floorplan.runner import execute_engine_request
from floorplan.runner import execute_engine_edit


def test_generation_checks_buildable_coordinates_and_returns_plot_coordinates():
    input_data = FloorPlanInput.model_validate({
        "plot": [40, 30],
        "setbacks": {
            "left": 3,
            "right": 2,
            "front": 4,
            "back": 1,
        },
        "entrance": "S",
        "north": "up",
        "rooms": [
            {"name": "living_room", "type": "living"}
        ],
        "pins": [],
    })

    # Mock P1: room starts at the buildable area's bottom-left corner.
    def mock_solver(**kwargs):
        return {
            "status": "success",
            "rooms": [
                {
                    "name": "living_room",
                    "x": 0,
                    "y": 0,
                    "w": 8,
                    "h": 6,
                }
            ],
            "hallway_segments": [],
            "messages": [],
        }

    checker_received = {}

    # Mock P4: capture the coordinates it receives.
    def mock_checker(input_payload, layout_payload):
        checker_received["layout"] = layout_payload
        return []

    result = execute_pipeline(
        input_data=input_data,
        solver_func=mock_solver,
        checker_func=mock_checker,
    )

    # The pipeline must succeed.
    assert not isinstance(result, ErrorResponse)

    # P4 must receive buildable coordinates.
    checked_room = checker_received["layout"]["rooms"][0]
    assert checked_room["x"] == 0
    assert checked_room["y"] == 0

    # The returned layout must use plot coordinates.
    output_room = result.layouts[0].rooms[0]
    assert output_room.x == 3
    assert output_room.y == 4

    # Room dimensions must remain unchanged.
    assert output_room.w == 8
    assert output_room.h == 6

    # The response must declare its coordinate system.
    assert result.coordinate_system == "plot"


def test_engine_request_converts_every_layout_to_plot_coordinates():
    input_data = FloorPlanInput.model_validate({
        "plot": [40, 30],
        "setbacks": {
            "left": 3,
            "right": 2,
            "front": 4,
            "back": 1,
        },
        "entrance": "S",
        "north": "up",
        "rooms": [
            {"name": "living_room", "type": "living"}
        ],
        "pins": [],
    })

    def mock_engine(*args, **kwargs):
        return {
            "status": "valid",
            "layouts": [
                {
                    "rooms": [
                        {
                            "name": "living_room",
                            "type": "living",
                            "x": 0,
                            "y": 0,
                            "w": 8,
                            "h": 6,
                        }
                    ],
                    "hallway_segments": [],
                },
                {
                    "rooms": [
                        {
                            "name": "living_room",
                            "type": "living",
                            "x": 5,
                            "y": 6,
                            "w": 8,
                            "h": 6,
                        }
                    ],
                    "hallway_segments": [],
                },
            ],
        }

    result = execute_engine_request(
        input_data=input_data,
        engine_func=mock_engine,
    )

    assert not isinstance(result, ErrorResponse)
    assert len(result.layouts) == 2

    first_room = result.layouts[0].rooms[0]
    second_room = result.layouts[1].rooms[0]

    assert (first_room.x, first_room.y) == (3, 4)
    assert (second_room.x, second_room.y) == (8, 10)

    assert result.coordinate_system == "plot"


def test_engine_edit_converts_plot_coordinates_to_buildable_before_editing():
    request = {
        "input": {
            "plot": [40, 30],
            "setbacks": {
                "left": 3,
                "right": 2,
                "front": 4,
                "back": 1,
            },
            "entrance": "S",
            "north": "up",
            "rooms": [
                {"name": "living_room", "type": "living"}
            ],
            "pins": [],
        },
        "layout": {
            "rooms": [
                {
                    "name": "living_room",
                    "type": "living",
                    "x": 3,
                    "y": 4,
                    "w": 8,
                    "h": 6,
                }
            ],
            "hallway_segments": [],
        },
        "edits": {
            "living_room": {
                "width": 9
            }
        },
        "lock": [],
    }

    engine_received = {}

    def mock_edit(*args, **kwargs):
        engine_received["input"] = args[0]
        engine_received["layout"] = args[1]
        engine_received["edits"] = args[2]
        engine_received["lock"] = kwargs.get("lock")

        return {
            "status": "valid",
            "layouts": [
                {
                    "rooms": [
                        {
                            "name": "living_room",
                            "type": "living",
                            "x": 0,
                            "y": 0,
                            "w": 8,
                            "h": 6,
                        }
                    ],
                    "hallway_segments": [],
                }
            ],
        }
    
    result = execute_engine_edit(
        request=request,
        edit_func=mock_edit,
    )

    assert not isinstance(result, ErrorResponse)

    # Engine must receive buildable coordinates.
    engine_room = engine_received["layout"]["rooms"][0]
    assert engine_room["x"] == 0
    assert engine_room["y"] == 0

    # Engine output must be converted back to plot coordinates.
    output_room = result.layouts[0].rooms[0]
    assert output_room.x == 3
    assert output_room.y == 4

    assert result.coordinate_system == "plot"


def test_repeated_edits_do_not_accumulate_setback_offsets():
    input_data = {
        "plot": [40, 30],
        "setbacks": {
            "left": 3,
            "right": 2,
            "front": 4,
            "back": 1,
        },
        "entrance": "S",
        "north": "up",
        "rooms": [
            {"name": "living_room", "type": "living"}
        ],
        "pins": [],
    }

    def make_request(layout):
        return {
            "input": input_data,
            "layout": layout,
            "edits": {
                "living_room": {
                    "width": 9
                }
            },
            "lock": [],
        }

    # Initial layout received from the frontend (plot coordinates).
    initial_layout = {
        "rooms": [
            {
                "name": "living_room",
                "type": "living",
                "x": 3,
                "y": 4,
                "w": 8,
                "h": 6,
            }
        ],
        "hallway_segments": [],
    }

    engine_positions = []

    def mock_edit(*args, **kwargs):
        room = args[1]["rooms"][0]

        engine_positions.append((room["x"], room["y"]))

        # Engine always returns buildable coordinates.
        return {
            "status": "valid",
            "layouts": [
                {
                    "rooms": [
                        {
                            "name": "living_room",
                            "type": "living",
                            "x": 0,
                            "y": 0,
                            "w": 8,
                            "h": 6,
                        }
                    ],
                    "hallway_segments": [],
                }
            ],
        }

    # First edit.
    first_result = execute_engine_edit(
        request=make_request(initial_layout),
        edit_func=mock_edit,
    )

    assert not isinstance(first_result, ErrorResponse)

    # Use the first result as the frontend would for the second edit.
    second_result = execute_engine_edit(
        request=make_request(first_result.layouts[0].model_dump()),
        edit_func=mock_edit,
    )

    assert not isinstance(second_result, ErrorResponse)

    # Both engine calls must receive buildable coordinates.
    assert engine_positions == [(0, 0), (0, 0)]

    # Both responses must retain plot coordinates.
    for result in (first_result, second_result):
        room = result.layouts[0].rooms[0]
        assert (room.x, room.y) == (3, 4)
        assert result.coordinate_system == "plot"


def test_engine_error_response_is_not_coordinate_converted():
    input_data = FloorPlanInput.model_validate({
        "plot": [40, 30],
        "setbacks": {
            "left": 3,
            "right": 2,
            "front": 4,
            "back": 1,
        },
        "entrance": "S",
        "north": "up",
        "rooms": [
            {"name": "living_room", "type": "living"}
        ],
        "pins": [],
    })

    error_payload = {
        "status": "infeasible",
        "messages": ["No valid layout found."],
        "layouts": [],
        "nearest": {"living_room": [8, 6]},
    }

    def mock_engine(*args, **kwargs):
        return error_payload

    result = execute_engine_request(
        input_data=input_data,
        engine_func=mock_engine,
    )

    assert isinstance(result, ErrorResponse)

    assert result.status == "infeasible"
    assert result.error_code == "INFEASIBLE"

    # Error details should retain the original engine information.
    assert result.details == error_payload


def test_engine_request_converts_rooms_hallways_doors_and_windows():
    input_data = FloorPlanInput.model_validate({
        "plot": [40, 30],
        "setbacks": {
            "left": 3,
            "right": 2,
            "front": 4,
            "back": 1,
        },
        "entrance": "S",
        "north": "up",
        "rooms": [
            {"name": "living_room", "type": "living"}
        ],
        "pins": [],
    })

    def mock_engine(*args, **kwargs):
        return {
            "status": "valid",
            "layouts": [
                {
                    "rooms": [
                        {
                            "name": "living_room",
                            "type": "living",
                            "x": 0,
                            "y": 0,
                            "w": 8,
                            "h": 6,
                        }
                    ],
                    "hallway_segments": [
                        {
                            "id": "hallway_1",
                            "x": 8,
                            "y": 0,
                            "w": 3,
                            "h": 12,
                        }
                    ],
                    "doors": [
                        {
                            "id": "door_1",
                            "x": 2,
                            "y": 0,
                            "width": 3,
                            "between": ["living_room", "hallway_1"],
                        }
                    ],
                    "windows": [
                        {
                            "id": "window_1",
                            "x": 4,
                            "y": 6,
                            "width": 4,
                            "room": "living_room",
                            "wall": "N",
                        }
                    ],
                }
            ],
        }

    result = execute_engine_request(
        input_data=input_data,
        engine_func=mock_engine,
    )

    assert not isinstance(result, ErrorResponse)

    layout = result.layouts[0]

    assert (layout.rooms[0].x, layout.rooms[0].y) == (3, 4)

    assert (
        layout.hallway_segments[0].x,
        layout.hallway_segments[0].y,
    ) == (11, 4)

    assert (layout.doors[0].x, layout.doors[0].y) == (5, 4)

    assert (layout.windows[0].x, layout.windows[0].y) == (7, 10)

    assert result.coordinate_system == "plot"
