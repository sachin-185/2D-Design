import copy
import json
from pathlib import Path

from floorplan.connections import required_pairs
from floorplan.connections_check import (
    check_bedroom_through_bedroom,
    check_required_connections,
    expected_connections,
)
from validate_all import validate_all
from validate_file import EXIT_VALID, main as validate_file_main

FOLDER = Path(__file__).parent / "TestCases"

# t02: buildable 20 x 25. The layout basic_layout.py produced, written out by hand.
INPUT = {
    "plot": [24, 30],
    "setbacks": {"front": 3, "back": 2, "left": 2, "right": 2},
    "entrance": "S",
    "north": "up",
    "rooms": [
        {"name": "living", "type": "living"},
        {"name": "kitchen", "type": "kitchen"},
        {"name": "bedroom", "type": "bedroom"},
        {"name": "bathroom", "type": "bathroom"},
    ],
}
GOOD = {
    "rooms": [
        {"name": "living", "x": 0, "y": 0, "w": 12, "h": 12},
        {"name": "kitchen", "x": 12, "y": 0, "w": 8, "h": 12},
        {"name": "bedroom", "x": 5, "y": 15, "w": 15, "h": 10},
        {"name": "bathroom", "x": 0, "y": 15, "w": 5, "h": 10},
    ],
    "hallway": {"x": 0, "y": 12, "w": 20, "h": 3},
}


def moved(room_name, **changes):
    layout = copy.deepcopy(GOOD)
    next(r for r in layout["rooms"] if r["name"] == room_name).update(changes)
    return layout


def codes(problems):
    return sorted({p["code"] for p in problems})


# --- which pairs must connect -------------------------------------------------

def test_expected_pairs_for_the_standard_rooms():
    assert expected_connections(INPUT) == [
        ("living", "hallway"),
        ("bedroom", "hallway"),
        ("bathroom", "hallway"),
        ("kitchen", "living"),
    ]

def test_two_bedrooms_both_need_the_hallway():
    inp = {
        **INPUT,
        "rooms": INPUT["rooms"] + [
            {"name": "bedroom2", "type": "bedroom"}
        ]
    }

    assert ("bedroom2", "hallway") in expected_connections(inp)

def test_no_living_room_means_no_kitchen_pair():
    inp = {**INPUT, "rooms": [r for r in INPUT["rooms"] if r["type"] != "living"]}
    assert all(b != "living" for _, b in expected_connections(inp))


def test_solver_side_and_checker_side_agree_on_every_test_file():
    """The two lists are written separately on purpose. If they ever differ, one has a bug."""
    for path in sorted(FOLDER.glob("*.json")):
        inp = json.load(open(path))["input"]
        assert sorted(required_pairs(inp)) == sorted(expected_connections(inp)), path.name


# --- checking a layout --------------------------------------------------------

def test_good_layout_meets_every_required_connection():
    assert check_required_connections(INPUT, GOOD) == []


def test_bedroom_pulled_away_from_hallway_is_reported_with_its_wall_length():
    found = check_required_connections(INPUT, moved("bedroom", y=17))
    assert [p["rooms"] for p in found] == [["bedroom", "hallway_1", "living"]]
    assert "shares 0 ft with the hallway network and 0 ft with a living room" in found[0]["message"]
    assert found[0]["code"] == "H6"


def test_wall_shorter_than_a_door_is_reported():
    found = check_required_connections(INPUT, moved("bathroom", w=2))  # 2 ft wall on the hallway
    assert [p["rooms"] for p in found] == [["bathroom", "hallway_1", "living"]]
    assert "shares 2 ft with the hallway network" in found[0]["message"]


def test_kitchen_not_touching_living_is_reported():
    found = check_required_connections(INPUT, moved("kitchen", x=14, w=6))
    assert [p["rooms"] for p in found] == [["kitchen", "living"]]


def test_no_hallway_reports_only_rooms_that_touch_neither_hallway_nor_living():
    # GOOD without its hallway: bedroom and bathroom sit 3 ft above the living room, so they fail.
    # The living room has no hallway requirement when there is no hallway.
    found = check_required_connections(INPUT, {"rooms": GOOD["rooms"]})
    assert [p["rooms"][0] for p in found] == ["bedroom", "bathroom"]
    assert all("the layout has no hallway" in p["message"] for p in found)


# --- hallway optional; bedrooms and bathrooms may use the living room instead (open decision 8) --

def rect(name, x, y, w, h):
    return {"name": name, "x": x, "y": y, "w": w, "h": h}


def h6_rooms(problems):
    """The room each H6 problem is about (the first name in its rooms list)."""
    return [p["rooms"][0] for p in problems if p["code"] == "H6"]


# Buildable 24 x 22, no hallway, fully covered, every size inside the table:
#   bathroom (0,12) 8 x 10 | bedroom (8,12) 16 x 10      both sit on the living room's top wall
#   living   (0,0) 16 x 12 | kitchen (16,0) 8 x 12       living touches the south (entrance) edge
NO_HALL_INPUT = {
    "plot": [24, 22],
    "setbacks": {"front": 0, "back": 0, "left": 0, "right": 0},
    "entrance": "S",
    "north": "up",
    "rooms": [
        {"name": "living", "type": "living"},
        {"name": "kitchen", "type": "kitchen"},
        {"name": "bedroom", "type": "bedroom"},
        {"name": "bathroom", "type": "bathroom"},
    ],
}
NO_HALL = {"rooms": [
    rect("living", 0, 0, 16, 12),
    rect("kitchen", 16, 0, 8, 12),
    rect("bathroom", 0, 12, 8, 10),
    rect("bedroom", 8, 12, 16, 10),
]}


def no_hall_with(**rooms):
    """NO_HALL with some rooms replaced: no_hall_with(bedroom=rect(...))."""
    layout = copy.deepcopy(NO_HALL)
    layout["rooms"] = [rooms.get(r["name"], r) for r in layout["rooms"]]
    return layout


def test_no_hallway_bedroom_and_bathroom_on_the_living_room_pass():
    assert check_required_connections(NO_HALL_INPUT, NO_HALL) == []
    assert h6_rooms(validate_all(NO_HALL_INPUT, NO_HALL)) == []


def test_no_hallway_bedroom_touching_only_the_kitchen_fails():
    layout = no_hall_with(bedroom=rect("bedroom", 16, 12, 8, 10))  # on the kitchen, corner with living
    found = check_required_connections(NO_HALL_INPUT, layout)
    assert h6_rooms(found) == ["bedroom"]
    assert found[0]["rooms"] == ["bedroom", "living"]


def test_no_hallway_bathroom_touching_nothing_fails():
    found = check_required_connections(NO_HALL_INPUT, no_hall_with(bathroom=rect("bathroom", 0, 40, 8, 10)))
    assert h6_rooms(found) == ["bathroom"]
    assert "shares 0 ft with the hallway network (the layout has no hallway) and 0 ft" in found[0]["message"]


def test_no_hallway_living_room_needs_nothing():
    inp = {**NO_HALL_INPUT, "rooms": [{"name": "living", "type": "living"}]}
    assert check_required_connections(inp, {"rooms": [rect("living", 0, 0, 16, 12)]}) == []


# Hallway present: living (0,0) 12 x 12, hallway_1 (12,0) 3 x 12 on its right, bathroom (15,0) on the hallway.
HALL_INPUT = {**NO_HALL_INPUT, "rooms": [
    {"name": "living", "type": "living"},
    {"name": "bedroom", "type": "bedroom"},
    {"name": "bathroom", "type": "bathroom"},
]}


def hall_layout(bedroom, living=None):
    return {
        "rooms": [living or rect("living", 0, 0, 12, 12), bedroom, rect("bathroom", 15, 0, 6, 8)],
        "hallway_segments": [{"id": "hallway_1", "x": 12, "y": 0, "w": 3, "h": 12}],
    }


def test_hallway_present_bedroom_touching_only_the_living_room_passes():
    layout = hall_layout(rect("bedroom", 0, 12, 12, 10))  # 12 ft on living, only a corner on the hallway
    assert check_required_connections(HALL_INPUT, layout) == []


def test_hallway_present_bedroom_touching_only_the_hallway_passes():
    layout = hall_layout(rect("bedroom", 15, 8, 10, 10))  # 4 ft on the hallway, nothing on living
    assert check_required_connections(HALL_INPUT, layout) == []


def test_hallway_present_bedroom_touching_neither_fails():
    found = check_required_connections(HALL_INPUT, hall_layout(rect("bedroom", 30, 30, 10, 10)))
    assert h6_rooms(found) == ["bedroom"]
    assert found[0]["rooms"] == ["bedroom", "hallway_1", "living"]
    assert "needs 3 ft with one of them" in found[0]["message"]


def test_hallway_present_living_room_away_from_the_hallway_fails():
    layout = hall_layout(rect("bedroom", 15, 8, 10, 10), living=rect("living", 0, 0, 10, 12))  # 2 ft gap
    found = check_required_connections(HALL_INPUT, layout)
    assert h6_rooms(found) == ["living"]
    assert found[0]["rooms"] == ["living", "hallway_1"]


def test_bedroom_with_2_ft_on_the_living_room_and_no_hallway_contact_fails():
    layout = hall_layout(rect("bedroom", -8, 12, 10, 10))  # overlaps living's top wall by 2 ft only
    found = check_required_connections(HALL_INPUT, layout)
    assert h6_rooms(found) == ["bedroom"]
    assert "shares 0 ft with the hallway network and 2 ft with a living room; needs 3 ft" in found[0]["message"]


def test_no_living_room_and_no_hallway_reports_the_bedroom_without_crashing():
    inp = {**NO_HALL_INPUT, "plot": [18, 10], "rooms": [
        {"name": "bedroom", "type": "bedroom"},
        {"name": "kitchen", "type": "kitchen"},
    ]}
    layout = {"rooms": [rect("bedroom", 0, 0, 10, 10), rect("kitchen", 10, 0, 8, 10)]}
    found = check_required_connections(inp, layout)
    assert h6_rooms(found) == ["bedroom"]
    assert "the layout has no living room" in found[0]["message"]
    assert "bedroom" in h6_rooms(validate_all(inp, layout))


def test_complete_no_hallway_layout_is_valid_in_validate_all_and_validate_file(tmp_path):
    assert validate_all(NO_HALL_INPUT, NO_HALL) == []  # no errors and no warnings (fully covered)
    input_path, layout_path = tmp_path / "input.json", tmp_path / "layout.json"
    input_path.write_text(json.dumps(NO_HALL_INPUT), encoding="utf-8")
    layout_path.write_text(json.dumps(NO_HALL), encoding="utf-8")
    assert validate_file_main([str(input_path), str(layout_path)]) == EXIT_VALID


# --- F1: bedroom only through another bedroom ---------------------------------

BEDROOM_INPUT = {**INPUT, "rooms": [
    {"name": "living", "type": "living"},
    {"name": "bedroom1", "type": "bedroom"},
    {"name": "bedroom2", "type": "bedroom"},
]}
# bedroom2 touches only bedroom1. Everything is reachable, but only by walking through bedroom1.
CHAIN = {
    "rooms": [
        {"name": "living", "x": 0, "y": 0, "w": 10, "h": 10},
        {"name": "bedroom1", "x": 0, "y": 10, "w": 10, "h": 10},
        {"name": "bedroom2", "x": 0, "y": 20, "w": 10, "h": 10},
    ],
    "hallway": {"x": 10, "y": 0, "w": 4, "h": 10},
}


def test_bedroom_behind_another_bedroom_is_reported():
    found = check_bedroom_through_bedroom(BEDROOM_INPUT, CHAIN, "living")
    assert [p["rooms"] for p in found] == [["bedroom2"]] and found[0]["code"] == "F1"


def test_walking_into_a_bedroom_is_fine_when_each_touches_the_hallway():
    layout = copy.deepcopy(CHAIN)
    layout["hallway"] = {"x": 10, "y": 0, "w": 4, "h": 30}  # now touches both bedrooms
    assert check_bedroom_through_bedroom(BEDROOM_INPUT, layout, "living") == []


# --- everything together ------------------------------------------------------

def test_validate_all_passes_the_good_layout():
    assert validate_all(INPUT, GOOD) == []


def test_validate_all_reports_every_layer_at_once():
    # Bedroom moved to x 6-20, y 17-25: 1 ft from the bathroom, 2 ft from the hallway, so it touches nothing.
    problems = validate_all(INPUT, moved("bedroom", x=6, y=17, w=14, h=8))
    assert {"H2", "H4", "H6", "F5"} <= set(codes(problems))
