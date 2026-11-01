from floorplan.connections import required_pairs
from floorplan.connections_check import (
    check_hallway_connectivity,
    check_hallway_shape,
    check_no_gaps,
    check_required_connections,
    expected_connections,
)
from validate_all import adapt_solver_result


INPUT = {
    "plot": [30, 20],
    "setbacks": {"left": 0, "right": 0, "front": 0, "back": 0},
    "entrance": "S",
    "north": "up",
    "rooms": [
        {"name": "living", "type": "living"},
        {"name": "bedroom_1", "type": "bedroom"},
        {"name": "kitchen", "type": "kitchen"},
    ],
}


CONNECTED_LAYOUT = {
    "rooms": [
        {"name": "living", "x": 0, "y": 0, "w": 12, "h": 12},
        {"name": "bedroom_1", "x": 15, "y": 10, "w": 10, "h": 10},
        {"name": "kitchen", "x": 12, "y": 0, "w": 3, "h": 10},
    ],
    "hallway_segments": [
        {"id": "hallway_1", "x": 0, "y": 12, "w": 12, "h": 3},
        {"id": "hallway_2", "x": 9, "y": 15, "w": 3, "h": 6},
    ],
}


def test_solver_and_checker_connection_contract_uses_generic_hallway():
    assert required_pairs(INPUT) == expected_connections(INPUT)
    assert ("living", "hallway") in required_pairs(INPUT)
    assert ("bedroom_1", "hallway") in required_pairs(INPUT)


def test_hallway_segments_can_connect_in_an_l_shape():
    assert check_hallway_connectivity(CONNECTED_LAYOUT) == []


def test_disconnected_hallway_segments_are_rejected():
    layout = {
        "rooms": [],
        "hallway_segments": [
            {"id": "hallway_1", "x": 0, "y": 0, "w": 12, "h": 3},
            {"id": "hallway_2", "x": 20, "y": 15, "w": 3, "h": 6},
        ],
    }
    problems = check_hallway_connectivity(layout)
    assert any(problem["code"] == "HW2" for problem in problems)


def test_total_corridor_length_is_combined_across_segments():
    layout = {
        "rooms": [],
        "hallway_segments": [
            {"id": "hallway_1", "x": 0, "y": 0, "w": 6, "h": 3},
            {"id": "hallway_2", "x": 3, "y": 3, "w": 3, "h": 6},
        ],
    }
    assert check_hallway_shape(layout) == []


def test_room_can_connect_to_any_hallway_segment():
    layout = {
        "rooms": [
            {"name": "living", "x": 0, "y": 0, "w": 12, "h": 12},
            {"name": "bedroom_1", "x": 15, "y": 10, "w": 10, "h": 10},
            {"name": "kitchen", "x": 12, "y": 0, "w": 3, "h": 10},
        ],
        "hallway_segments": [
            {"id": "hallway_1", "x": 0, "y": 12, "w": 12, "h": 3},
            {"id": "hallway_2", "x": 12, "y": 10, "w": 3, "h": 6},
        ],
    }
    # The living room touches hallway_1; the bedroom touches hallway_2.
    assert check_required_connections(INPUT, layout) == []


def test_partial_coverage_is_a_warning_not_a_hard_error():
    inp = {"plot": [20, 20], "rooms": []}
    layout = {"rooms": [{"name": "room", "x": 0, "y": 0, "w": 10, "h": 10}]}
    problems = check_no_gaps(inp, layout)
    assert len(problems) == 1
    assert problems[0]["code"] == "H4"
    assert problems[0]["severity"] == "warning"


def test_adapter_preserves_multiple_hallway_segments():
    result = {
        "status": "success",
        "rooms": {"living": {"x": 0, "y": 0, "w": 12, "h": 12}},
        "hallway_segments": [
            {"id": "hallway_1", "x": 0, "y": 12, "w": 12, "h": 3},
            {"id": "hallway_2", "x": 9, "y": 15, "w": 3, "h": 6},
        ],
    }
    adapted = adapt_solver_result(result)
    assert len(adapted["hallway_segments"]) == 2
    assert adapted["hallway_segments"][1]["id"] == "hallway_2"


def test_two_foot_hallway_contact_does_not_count_as_connected():
    layout = {
        "rooms": [],
        "hallway_segments": [
            {"id": "hallway_1", "x": 0, "y": 0, "w": 10, "h": 3},
            {"id": "hallway_2", "x": 8, "y": 3, "w": 3, "h": 6},
        ],
    }
    problems = check_hallway_connectivity(layout)
    assert any(problem["code"] == "HW2" for problem in problems)


def test_multi_segment_layout_passes_hard_checks_and_warns_on_partial_coverage():
    from validate_all import validate_all

    inp = {
        "plot": [30, 24],
        "setbacks": {"left": 0, "right": 0, "front": 0, "back": 0},
        "entrance": "S",
        "north": "up",
        "rooms": [
            {"name": "living", "type": "living"},
            {"name": "kitchen", "type": "kitchen"},
            {"name": "bedroom_1", "type": "bedroom"},
        ],
    }
    layout = {
        "rooms": [
            {"name": "living", "x": 0, "y": 0, "w": 12, "h": 12},
            {"name": "kitchen", "x": 12, "y": 0, "w": 8, "h": 10},
            {"name": "bedroom_1", "x": 15, "y": 12, "w": 10, "h": 10},
        ],
        "hallway_segments": [
            {"id": "hallway_1", "x": 0, "y": 12, "w": 12, "h": 3},
            {"id": "hallway_2", "x": 12, "y": 12, "w": 3, "h": 6},
        ],
    }
    problems = validate_all(inp, layout)
    assert all(problem.get("severity", "error") == "warning" for problem in problems)
    assert any(problem["code"] == "H4" for problem in problems)

def test_validate_all_rejects_hallway_with_5x5_square():
    from validate_all import validate_all

    inp = {
        **INPUT,
        "plot": [30, 20],
    }

    layout = {
        "rooms": [],
        "hallway_segments": [
            {"id": "hallway_1", "x": 0, "y": 10, "w": 10, "h": 3},
            {"id": "hallway_2", "x": 0, "y": 13, "w": 10, "h": 4},
        ],
    }

    problems = validate_all(inp, layout)

    assert any(
        problem["code"] == "HW3"
        for problem in problems
    )