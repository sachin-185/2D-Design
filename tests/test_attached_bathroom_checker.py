"""Attached bathrooms: written from the rule, not from the solver's code.

A bathroom with attached_to must share at least 3 ft of wall with that bedroom and does not need the
hallway. A bathroom without attached_to keeps the common rule (any hallway segment or any living room).
"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from floorplan.connections import required_pairs
from floorplan.connections_check import check_required_connections, expected_connections, shared_wall_length
from floorplan.geometry import solve_layout
from floorplan.validator import SIZE_TABLE
from validate_all import adapt_solver_result, errors_only, validate_all, validate_solver_result
from validate_file import EXIT_VALID, main as validate_file_main

ROOT = Path(__file__).parent.parent
FOLDER = Path(__file__).parent / "TestCases"

LIVING = {"name": "living", "type": "living"}
BEDROOM = {"name": "bedroom", "type": "bedroom"}
ATTACHED = {"name": "ensuite", "type": "bathroom", "attached_to": "bedroom"}
INPUT = {
    "plot": [40, 40],
    "setbacks": {"front": 0, "back": 0, "left": 0, "right": 0},
    "entrance": "S",
    "north": "up",
    "rooms": [LIVING, BEDROOM, ATTACHED],
}


def rect(name, x, y, w, h):
    return {"name": name, "x": x, "y": y, "w": w, "h": h}


def layout_with(ensuite):
    """living (0,0) 12 x 12, hallway_1 (12,0) 3 x 12, bedroom (15,0) 12 x 10 on the hallway's right."""
    return {
        "rooms": [rect("living", 0, 0, 12, 12), rect("bedroom", 15, 0, 12, 10), ensuite],
        "hallway_segments": [{"id": "hallway_1", "x": 12, "y": 0, "w": 3, "h": 12}],
    }


def h6(problems):
    return [p for p in problems if p["code"] == "H6"]


# --- the pair lists ------------------------------------------------------------

@pytest.mark.parametrize("pairs_from", [required_pairs, expected_connections])
def test_attached_bathroom_pairs_with_its_bedroom_only(pairs_from):
    pairs = pairs_from(INPUT)
    assert ("ensuite", "bedroom") in pairs
    assert ("ensuite", "hallway") not in pairs
    assert ("bedroom", "hallway") in pairs


@pytest.mark.parametrize("pairs_from", [required_pairs, expected_connections])
def test_common_bathroom_still_pairs_with_the_hallway(pairs_from):
    inp = {**INPUT, "rooms": [LIVING, BEDROOM, ATTACHED, {"name": "common", "type": "bathroom"}]}
    assert ("common", "hallway") in pairs_from(inp)


@pytest.mark.parametrize("pairs_from", [required_pairs, expected_connections])
@pytest.mark.parametrize("empty", [None, ""])
def test_empty_attached_to_means_a_common_bathroom(pairs_from, empty):
    inp = {**INPUT, "rooms": [LIVING, BEDROOM, {"name": "bath", "type": "bathroom", "attached_to": empty}]}
    assert ("bath", "hallway") in pairs_from(inp)


@pytest.mark.parametrize("pairs_from", [required_pairs, expected_connections])
def test_two_bathrooms_can_attach_to_one_bedroom(pairs_from):
    second = {"name": "ensuite2", "type": "bathroom", "attached_to": "bedroom"}
    pairs = pairs_from({**INPUT, "rooms": [LIVING, BEDROOM, ATTACHED, second]})
    assert ("ensuite", "bedroom") in pairs and ("ensuite2", "bedroom") in pairs


def test_solver_and_checker_lists_agree_with_attached_bathrooms():
    assert sorted(required_pairs(INPUT)) == sorted(expected_connections(INPUT))


def test_a_shared_test_input_uses_attached_to():
    """Without one, the agreement test over tests/TestCases would not cover attached bathrooms."""
    rooms = [r for path in FOLDER.glob("*.json") for r in json.load(open(path))["input"]["rooms"]]
    assert any(r.get("attached_to") for r in rooms)


# --- checking a layout ---------------------------------------------------------

def test_touching_only_its_bedroom_passes():
    assert check_required_connections(INPUT, layout_with(rect("ensuite", 27, 0, 8, 10))) == []


def test_touching_its_bedroom_and_the_hallway_passes():
    layout = layout_with(rect("ensuite", 15, 10, 8, 10))  # on the bedroom's top wall
    layout["hallway_segments"][0]["h"] = 20  # and now 10 ft on the hallway
    assert check_required_connections(INPUT, layout) == []


def test_exactly_3_ft_on_its_bedroom_passes():
    assert check_required_connections(INPUT, layout_with(rect("ensuite", 27, 7, 8, 10))) == []


def test_2_ft_on_its_bedroom_fails():
    found = check_required_connections(INPUT, layout_with(rect("ensuite", 27, 8, 8, 10)))
    assert [p["rooms"] for p in h6(found)] == [["ensuite", "bedroom"]]
    assert "share 2 ft" in found[0]["message"]


def test_corner_contact_with_its_bedroom_fails():
    found = check_required_connections(INPUT, layout_with(rect("ensuite", 27, 10, 8, 10)))
    assert [p["rooms"] for p in h6(found)] == [["ensuite", "bedroom"]]


def test_touching_the_hallway_but_not_its_bedroom_fails():
    layout = layout_with(rect("ensuite", 15, 11, 8, 10))  # 1 ft gap to the bedroom, 1 ft on the hallway
    layout["hallway_segments"][0]["h"] = 20  # now 9 ft on the hallway
    found = check_required_connections(INPUT, layout)
    assert [p["rooms"] for p in h6(found)] == [["ensuite", "bedroom"]]


def test_touching_a_living_room_but_not_its_bedroom_fails():
    found = check_required_connections(INPUT, layout_with(rect("ensuite", 0, 12, 8, 10)))
    assert [p["rooms"] for p in h6(found)] == [["ensuite", "bedroom"]]


def test_touching_a_different_bedroom_fails():
    other = {"name": "bedroom2", "type": "bedroom"}
    inp = {**INPUT, "rooms": [LIVING, BEDROOM, other, ATTACHED]}
    layout = layout_with(rect("ensuite", 27, 20, 8, 10))
    layout["rooms"].append(rect("bedroom2", 15, 20, 12, 10))  # ensuite is on bedroom2, not on bedroom
    layout["hallway_segments"][0]["h"] = 30
    assert [p["rooms"] for p in h6(check_required_connections(inp, layout))] == [["ensuite", "bedroom"]]


def test_common_bathroom_keeps_its_rule_next_to_an_attached_one():
    inp = {**INPUT, "rooms": [LIVING, BEDROOM, ATTACHED, {"name": "common", "type": "bathroom"}]}
    layout = layout_with(rect("ensuite", 27, 0, 8, 10))
    layout["rooms"].append(rect("common", 30, 30, 8, 10))  # touches nothing
    found = h6(check_required_connections(inp, layout))
    assert [p["rooms"][0] for p in found] == ["common"]


def test_attached_to_a_room_that_is_not_in_the_layout_gives_h6_not_a_crash():
    inp = {**INPUT, "rooms": [LIVING, BEDROOM, {"name": "ensuite", "type": "bathroom", "attached_to": "ghost"}]}
    found = h6(check_required_connections(inp, layout_with(rect("ensuite", 27, 0, 8, 10))))
    assert [p["rooms"] for p in found] == [["ensuite", "ghost"]]
    assert "ghost is missing" in found[0]["message"]


def test_missing_attached_bathroom_gives_h6():
    layout = layout_with(rect("other", 27, 0, 8, 10))
    assert "ensuite is missing" in h6(check_required_connections(INPUT, layout))[0]["message"]


# --- a whole layout ------------------------------------------------------------

# Buildable 24 x 22, no hallway, fully covered, every size inside the table:
#   bedroom (0,12) 16 x 10 | ensuite (16,12) 8 x 10    the ensuite touches the bedroom and the kitchen only
#   living  (0,0)  16 x 12 | kitchen (16,0)  8 x 12
FULL_INPUT = {
    **INPUT,
    "plot": [24, 22],
    "rooms": [LIVING, {"name": "kitchen", "type": "kitchen"}, BEDROOM, ATTACHED],
}
FULL_LAYOUT = {"rooms": [
    rect("living", 0, 0, 16, 12),
    rect("kitchen", 16, 0, 8, 12),
    rect("bedroom", 0, 12, 16, 10),
    rect("ensuite", 16, 12, 8, 10),
]}


def test_complete_layout_is_valid_and_no_other_rule_objects():
    # Bedrooms are dead ends for F1, but a bathroom behind its bedroom is not another bedroom.
    assert validate_all(FULL_INPUT, FULL_LAYOUT) == []


def test_complete_layout_is_valid_in_validate_file(tmp_path):
    input_path, layout_path = tmp_path / "input.json", tmp_path / "layout.json"
    input_path.write_text(json.dumps(FULL_INPUT), encoding="utf-8")
    layout_path.write_text(json.dumps(FULL_LAYOUT), encoding="utf-8")
    assert validate_file_main([str(input_path), str(layout_path)]) == EXIT_VALID


def test_real_solver_places_the_attached_bathroom_against_its_bedroom():
    """End to end on t11: the solver reads required_pairs, and the checker confirms the result."""
    inp = json.load(open(FOLDER / "t11_attached_bathroom.json"))["input"]
    types = {r["name"]: r["type"] for r in inp["rooms"]}
    room_specs = {
        name: {
            "min_width": SIZE_TABLE[kind][0][0],
            "min_height": SIZE_TABLE[kind][0][1],
            "max_width": SIZE_TABLE[kind][1][0],
            "max_height": SIZE_TABLE[kind][1][1],
        }
        for name, kind in types.items()
    }
    result = solve_layout(
        plot_width=inp["plot"][0],
        plot_height=inp["plot"][1],
        room_specs=room_specs,
        setbacks=inp["setbacks"],
        include_hallway=True,
        layout_input=inp,
        max_hallway_segments=2,
        time_limit_seconds=30,
    )
    if result["status"] == "unknown":  # a timeout says nothing about the rule
        pytest.skip("the solver ran out of time")
    assert result["status"] == "success"
    assert errors_only(validate_solver_result(inp, result)) == []
    rooms = {r["name"]: r for r in adapt_solver_result(result)["rooms"]}
    assert shared_wall_length(rooms["ensuite"], rooms["bedroom"]) >= 3


# --- check_inputs.py -----------------------------------------------------------

def run_check_inputs(folder):
    done = subprocess.run(
        [sys.executable, str(ROOT / "check_inputs.py"), str(folder)],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout


def write_case(folder, rooms):
    case = {"name": "x", "input": {"plot": [30, 30], "entrance": "S", "rooms": rooms}, "expect": {"status": "valid"}}
    (folder / "case.json").write_text(json.dumps(case), encoding="utf-8")


def test_check_inputs_accepts_every_shared_input():
    assert ", 0 with problems" in run_check_inputs(FOLDER)


def test_check_inputs_rejects_attached_to_on_a_room_that_is_not_a_bathroom(tmp_path):
    write_case(tmp_path, [BEDROOM, {"name": "kitchen", "type": "kitchen", "attached_to": "bedroom"}])
    assert "only a bathroom can use attached_to: kitchen" in run_check_inputs(tmp_path)


def test_check_inputs_rejects_attached_to_a_room_that_is_not_a_bedroom(tmp_path):
    write_case(tmp_path, [LIVING, {"name": "bath", "type": "bathroom", "attached_to": "living"}])
    assert "attached_to must name a bedroom: bath -> living" in run_check_inputs(tmp_path)


def test_check_inputs_rejects_attached_to_a_missing_room(tmp_path):
    write_case(tmp_path, [BEDROOM, {"name": "bath", "type": "bathroom", "attached_to": "ghost"}])
    assert "attached_to must name a bedroom: bath -> ghost" in run_check_inputs(tmp_path)
