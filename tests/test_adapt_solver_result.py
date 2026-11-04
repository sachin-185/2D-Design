"""A broken solver result gives a clear ValueError from the adapter, never a crash in the checks."""
import json

import pytest

from validate_all import adapt_solver_result, validate_solver_result
from validate_file import EXIT_FILE_PROBLEM, main

INPUT = {
    "plot": [24, 22],
    "setbacks": {"left": 0, "right": 0, "front": 0, "back": 0},
    "entrance": "S",
    "north": "up",
    "rooms": [{"name": "living", "type": "living"}],
}


def result_with(**fields):
    room = {"x": 0, "y": 0, "width": 12, "height": 12}
    return {"status": "success", "rooms": {"living": room}, **fields}


def result_with_room(room):
    return {"status": "success", "rooms": {"living": room}}


GOOD_SEGMENT = {"id": "hallway_1", "x": 12, "y": 0, "w": 3, "h": 12}

BROKEN_RESULTS = [
    (result_with_room({"x": 0, "y": 0}), "room 'living' needs a whole number 'w'"),
    (result_with_room({"x": 0, "y": 0, "w": 12}), "room 'living' needs a whole number 'h'"),
    (result_with_room({"y": 0, "w": 12, "h": 12}), "room 'living' needs a whole number 'x'"),
    (result_with_room({"x": 0, "w": 12, "h": 12}), "room 'living' needs a whole number 'y'"),
    (result_with_room({"x": 0, "y": 0, "w": "12", "h": 12}), "needs a whole number 'w'"),
    (result_with_room({"x": 1.5, "y": 0, "w": 12, "h": 12}), "needs a whole number 'x'"),
    (result_with_room({"x": True, "y": 0, "w": 12, "h": 12}), "needs a whole number 'x'"),
    (result_with_room({"x": 0, "y": 0, "w": 0, "h": 12}), "positive width and height"),
    (result_with_room(5), "room 'living' must be a dictionary"),
    (result_with(hallway_segments={"id": "hallway_1"}), "'hallway_segments' must be a list"),
    (result_with(hallway_segments=[{"id": "hallway_1", "x": 12}]), "hallway segment 1 needs a whole number 'y'"),
    (result_with(hallway_segments=[GOOD_SEGMENT, "oops"]), "hallway segment 2 must be a dictionary"),
    (result_with(hallway={"x": 12, "y": 0, "w": 3}), "hallway needs a whole number 'h'"),
]


@pytest.mark.parametrize("result, expected", BROKEN_RESULTS)
def test_broken_result_raises_a_clear_value_error(result, expected):
    with pytest.raises(ValueError, match=expected):
        adapt_solver_result(result)
    with pytest.raises(ValueError, match=expected):
        validate_solver_result(INPUT, result)


@pytest.mark.parametrize("result, expected", BROKEN_RESULTS)
def test_validate_file_reports_a_file_problem_for_the_same_results(tmp_path, capsys, result, expected):
    input_path, layout_path = tmp_path / "input.json", tmp_path / "layout.json"
    input_path.write_text(json.dumps(INPUT), encoding="utf-8")
    layout_path.write_text(json.dumps(result), encoding="utf-8")
    assert main([str(input_path), str(layout_path)]) == EXIT_FILE_PROBLEM
    assert expected in capsys.readouterr().err


def test_width_and_height_names_are_still_accepted():
    layout = adapt_solver_result(result_with())
    assert layout["rooms"] == [{"name": "living", "x": 0, "y": 0, "w": 12, "h": 12}]


@pytest.mark.parametrize("no_hallway", [{"hallway_segments": []}, {"hallway": None}, {}])
def test_every_no_hallway_form_is_still_accepted(no_hallway):
    layout = adapt_solver_result(result_with(**no_hallway))
    assert "hallway_segments" not in layout and "hallway" not in layout


def test_good_segment_is_kept_with_its_extra_fields():
    segment = {**GOOD_SEGMENT, "area": 36}
    layout = adapt_solver_result(result_with(hallway_segments=[segment]))
    assert layout["hallway_segments"] == [segment]
    assert layout["hallway"] == segment  # one segment: the legacy field is still filled in


def test_good_legacy_hallway_is_kept():
    hallway = {"x": 12, "y": 0, "w": 3, "h": 12}
    assert adapt_solver_result(result_with(hallway=hallway))["hallway"] == hallway
