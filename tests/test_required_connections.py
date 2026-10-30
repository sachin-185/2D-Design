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
        ("living", "hallway_1"), ("bedroom", "hallway_1"), ("bathroom", "hallway_1"), ("kitchen", "living"),
    ]


def test_two_bedrooms_both_need_the_hallway():
    inp = {**INPUT, "rooms": INPUT["rooms"] + [{"name": "bedroom2", "type": "bedroom"}]}
    assert ("bedroom2", "hallway_1") in expected_connections(inp)


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
    assert [p["rooms"] for p in found] == [["bedroom", "hallway_1"]]
    assert "share 0 ft" in found[0]["message"] and found[0]["code"] == "H6"


def test_wall_shorter_than_a_door_is_reported():
    found = check_required_connections(INPUT, moved("bathroom", w=2))  # 2 ft wall on the hallway
    assert [p["rooms"] for p in found] == [["bathroom", "hallway_1"]]
    assert "share 2 ft" in found[0]["message"]


def test_kitchen_not_touching_living_is_reported():
    found = check_required_connections(INPUT, moved("kitchen", x=14, w=6))
    assert [p["rooms"] for p in found] == [["kitchen", "living"]]


def test_missing_hallway_is_reported_for_every_room_that_needs_it():
    layout = {"rooms": GOOD["rooms"]}
    found = check_required_connections(INPUT, layout)
    assert len(found) == 3 and all("hallway_1 is missing" in p["message"] for p in found)


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
