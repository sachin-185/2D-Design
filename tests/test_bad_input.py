"""Bad input must give a clear problem (code I1), not a crash."""
import copy

from floorplan.validator import check_input
from validate_all import validate_all

INPUT = {
    "plot": [30, 20],
    "setbacks": {"left": 0, "right": 0, "front": 0, "back": 0},
    "entrance": "S",
    "north": "up",
    "rooms": [
        {"name": "living", "type": "living"},
        {"name": "bedroom_1", "type": "bedroom"},
    ],
}

LAYOUT = {
    "rooms": [
        {"name": "living", "x": 0, "y": 0, "w": 12, "h": 12},
        {"name": "bedroom_1", "x": 12, "y": 3, "w": 12, "h": 12},
    ],
    "hallway_segments": [{"id": "hallway_1", "x": 0, "y": 12, "w": 12, "h": 3}],
}


def changed(**kw):
    inp = copy.deepcopy(INPUT)
    inp.update(kw)
    return inp


def test_good_input_has_no_input_problems():
    assert check_input(INPUT) == []


def test_lowercase_entrance_is_reported_not_a_crash():
    problems = validate_all(changed(entrance="s"), LAYOUT)
    assert [p["code"] for p in problems] == ["I1"]
    assert "entrance" in problems[0]["message"]


def test_missing_entrance_is_reported():
    inp = copy.deepcopy(INPUT)
    del inp["entrance"]
    assert [p["code"] for p in validate_all(inp, LAYOUT)] == ["I1"]


def test_bad_north_is_reported():
    problems = validate_all(changed(north="east"), LAYOUT)
    assert [p["code"] for p in problems] == ["I1"]
    assert "north" in problems[0]["message"]


def test_no_rooms_is_reported():
    problems = validate_all(changed(rooms=[]), LAYOUT)
    assert [p["code"] for p in problems] == ["I1"]


def test_room_named_hallway_is_reserved():
    rooms = INPUT["rooms"] + [{"name": "hallway", "type": "store"}]
    problems = validate_all(changed(rooms=rooms), LAYOUT)
    assert [p["code"] for p in problems] == ["I1"]
    assert problems[0]["rooms"] == ["hallway"]


def test_room_named_hallway_1_is_reserved():
    rooms = INPUT["rooms"] + [{"name": "hallway_1", "type": "store"}]
    assert [p["code"] for p in validate_all(changed(rooms=rooms), LAYOUT)] == ["I1"]


def test_names_that_only_look_similar_are_allowed():
    rooms = INPUT["rooms"] + [{"name": "hallway_store", "type": "store"}]
    assert check_input(changed(rooms=rooms)) == []


def test_duplicate_room_names_are_reported():
    rooms = INPUT["rooms"] + [{"name": "living", "type": "living"}]
    problems = validate_all(changed(rooms=rooms), LAYOUT)
    assert [p["code"] for p in problems] == ["I1"]
    assert "two rooms" in problems[0]["message"]


def test_input_problems_are_errors():
    assert validate_all(changed(entrance="x"), LAYOUT)[0]["severity"] == "error"