import copy

from floorplan.connections_check import (
    build_graph,
    check_no_gaps,
    check_reachability,
    reachable_rooms,
    shared_wall_length,
)

from floorplan.validator import check_inside_plot, check_no_overlap
from tests.test_validator import INPUT

# 24 x 32 buildable. Hallway runs along the middle; every room touches it. Fills the area exactly.
FULL = {
    "rooms": [
        {"name": "living", "x": 0, "y": 0, "w": 10, "h": 16},
        {"name": "kitchen", "x": 14, "y": 0, "w": 10, "h": 16},
        {"name": "bedroom", "x": 0, "y": 16, "w": 10, "h": 16},
        {"name": "bathroom", "x": 14, "y": 16, "w": 10, "h": 16},
    ],
    "hallway": {"x": 10, "y": 0, "w": 4, "h": 32},
}


def room(name, x, y, w, h):
    return {"name": name, "x": x, "y": y, "w": w, "h": h}


def test_full_layout_is_clean():
    assert check_inside_plot(INPUT, FULL) == []
    assert check_no_overlap(FULL) == []
    assert check_no_gaps(INPUT, FULL) == []
    assert check_reachability(FULL) == []


def test_shared_wall_side_by_side():
    assert shared_wall_length(room("a", 0, 0, 10, 10), room("b", 10, 4, 5, 10)) == 6


def test_shared_wall_one_above_other():
    assert shared_wall_length(room("a", 0, 0, 10, 10), room("b", 3, 10, 20, 5)) == 7


def test_corner_touch_is_not_a_wall():
    assert shared_wall_length(room("a", 0, 0, 10, 10), room("b", 10, 10, 5, 5)) == 0


def test_rooms_apart_share_nothing():
    assert shared_wall_length(room("a", 0, 0, 10, 10), room("b", 11, 0, 5, 10)) == 0


def test_graph_links_are_two_way():
    graph = build_graph(FULL)
    assert graph["hallway_1"] == {"living", "kitchen", "bedroom", "bathroom"}
    assert graph["living"] == {"hallway_1", "bedroom"}  # living and bedroom share a 10 ft wall
    assert "kitchen" not in graph["living"]  # 4 ft apart, the hallway sits between


def test_wall_shorter_than_door_is_not_a_connection():
    layout = {"rooms": [room("living", 0, 0, 10, 10), room("bedroom", 10, 8, 10, 10)]}  # 2 ft shared
    assert build_graph(layout)["living"] == set()
    assert build_graph(layout, door_min=2)["living"] == {"bedroom"}


def test_unreachable_bedroom_is_reported():
    layout = copy.deepcopy(FULL)
    layout["rooms"][2] = room("bedroom", 0, 18, 9, 14)  # 2 ft from living, 1 ft from the hallway
    found = check_reachability(layout)
    assert [v["rooms"] for v in found] == [["bedroom"]]
    assert found[0]["code"] == "F5"


def test_room_reached_only_through_another_room_still_counts():
    layout = {"rooms": [room("living", 0, 0, 10, 10), room("kitchen", 10, 0, 10, 10), room("store", 20, 0, 5, 10)]}
    assert check_reachability(layout) == []
    assert reachable_rooms(build_graph(layout), "living") == {"living", "kitchen", "store"}


def test_missing_entrance_room_is_reported():
    assert check_reachability(FULL, entrance_room="foyer")[0]["code"] == "F5"


def test_gap_is_reported_with_size():
    layout = copy.deepcopy(FULL)
    layout["rooms"][0]["h"] = 12  # 10 x 4 = 40 sq ft left empty
    found = check_no_gaps(INPUT, layout)
    assert found[0]["code"] == "H4" and "40 sq ft unused" in found[0]["message"]
