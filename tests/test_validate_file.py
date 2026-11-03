"""validate_file.py: one layout file checked from the command line, with clear exit codes."""
import copy
import json
from pathlib import Path

import pytest

from validate_all import adapt_solver_result
from validate_file import (
    EXIT_FILE_PROBLEM,
    EXIT_INVALID,
    EXIT_VALID,
    FileProblem,
    check_files,
    main,
)

REGRESSION_DIR = Path(__file__).parent / "regression"

# The input that produced tests/regression/latest_30x24_layout.json (no problems at all).
INPUT = {
    "plot": [30, 24],
    "setbacks": {"left": 0, "right": 0, "front": 0, "back": 0},
    "entrance": "S",
    "north": "up",
    "rooms": [
        {"name": "living", "type": "living"},
        {"name": "bedroom_1", "type": "bedroom"},
        {"name": "kitchen", "type": "kitchen"},
        {"name": "bathroom", "type": "bathroom"},
    ],
}


def solver_result():
    with open(REGRESSION_DIR / "latest_30x24_layout.json") as f:
        return json.load(f)


def checker_layout():
    return adapt_solver_result(solver_result())


def write(folder, name, data):
    path = folder / name
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return str(path)


def run(folder, inp, layout, *extra):
    """Write both files, run the command, return its exit code."""
    return main([write(folder, "input.json", inp), write(folder, "layout.json", layout), *extra])


# --- valid layouts in every supported format ---

def test_valid_checker_format(tmp_path, capsys):
    assert run(tmp_path, INPUT, checker_layout()) == EXIT_VALID
    assert "Result: VALID (0 errors, 0 warnings)" in capsys.readouterr().out


def test_valid_solver_result_format(tmp_path):
    assert run(tmp_path, INPUT, solver_result()) == EXIT_VALID


def test_valid_p3_output_format_picks_the_requested_layout(tmp_path):
    broken = copy.deepcopy(checker_layout())
    broken["rooms"][1]["x"] = broken["rooms"][0]["x"]  # overlap in layout 0 only
    broken["rooms"][1]["y"] = broken["rooms"][0]["y"]
    output = {"layouts": [broken, checker_layout()]}
    assert run(tmp_path, INPUT, output) == EXIT_INVALID
    assert run(tmp_path, INPUT, output, "--layout-index", "1") == EXIT_VALID


def test_test_case_file_uses_its_input_part(tmp_path):
    case = {"name": "example", "input": INPUT, "expect": {"status": "valid"}}
    assert run(tmp_path, case, checker_layout()) == EXIT_VALID


def test_file_saved_with_a_bom_is_read(tmp_path):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(INPUT), encoding="utf-8-sig")
    assert main([str(path), write(tmp_path, "layout.json", checker_layout())]) == EXIT_VALID


# --- warnings and errors ---

def test_warning_only_is_still_valid(tmp_path, capsys):
    layout = checker_layout()
    bathroom = next(r for r in layout["rooms"] if r["name"] == "bathroom")
    bathroom["w"] -= 1  # leaves a 1 ft strip unused: H4 warning, nothing else
    assert run(tmp_path, INPUT, layout) == EXIT_VALID
    out = capsys.readouterr().out
    assert "WARNINGS (1)" in out and "[H4]" in out and "ERRORS" not in out


def test_overlap_is_reported_and_invalid(tmp_path, capsys):
    layout = checker_layout()
    layout["rooms"][1]["x"], layout["rooms"][1]["y"] = layout["rooms"][0]["x"], layout["rooms"][0]["y"]
    assert run(tmp_path, INPUT, layout) == EXIT_INVALID
    out = capsys.readouterr().out
    assert "[H3]" in out and "Result: NOT VALID" in out


def test_bad_input_values_are_reported_as_i1(tmp_path, capsys):
    assert run(tmp_path, {**INPUT, "entrance": "X"}, checker_layout()) == EXIT_INVALID
    assert "[I1]" in capsys.readouterr().out


def test_json_output_can_be_parsed(tmp_path, capsys):
    layout = checker_layout()
    layout["rooms"][1]["x"], layout["rooms"][1]["y"] = layout["rooms"][0]["x"], layout["rooms"][0]["y"]
    assert run(tmp_path, INPUT, layout, "--json") == EXIT_INVALID
    report = json.loads(capsys.readouterr().out)
    assert report["valid"] is False
    assert any(p["code"] == "H3" for p in report["errors"])
    assert all(p["severity"] == "error" for p in report["errors"])


# --- file problems: clear message, exit code 2, never a crash ---

def test_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "nope.json"), write(tmp_path, "layout.json", checker_layout())]) \
        == EXIT_FILE_PROBLEM
    assert "file not found" in capsys.readouterr().err


def test_file_that_is_not_json(tmp_path, capsys):
    assert run(tmp_path, INPUT, "{ not json") == EXIT_FILE_PROBLEM
    assert "not valid JSON" in capsys.readouterr().err


@pytest.mark.parametrize("change, expected", [
    (lambda lay: lay["rooms"][0].pop("x"), "whole number 'x'"),
    (lambda lay: lay["rooms"][0].update(w=0), "positive width"),
    (lambda lay: lay["rooms"][0].update(y="3"), "whole number 'y'"),
    (lambda lay: lay["rooms"][0].pop("name"), "needs a 'name'"),
    (lambda lay: lay.update(hallway_segments={"id": "hallway_1"}), "must be a list"),
    (lambda lay: lay["hallway_segments"][0].pop("h"), "whole number 'h'"),
    (lambda lay: lay.pop("rooms"), "'rooms' list"),
])
def test_broken_layout_shape(tmp_path, capsys, change, expected):
    layout = checker_layout()
    change(layout)
    assert run(tmp_path, INPUT, layout) == EXIT_FILE_PROBLEM
    assert expected in capsys.readouterr().err


@pytest.mark.parametrize("change, expected", [
    (lambda inp: inp.pop("plot"), "'plot'"),
    (lambda inp: inp.update(plot=[30]), "'plot'"),
    (lambda inp: inp.update(setbacks={"left": -1}), "'setbacks'"),
    (lambda inp: inp.update(rooms={"living": "living"}), "'rooms' must be a list"),
    (lambda inp: inp["rooms"][0].pop("type"), "needs a 'name' and a 'type'"),
    (lambda inp: inp.update(pins=[{"width": 12}]), "'pins'"),
])
def test_broken_input_shape(tmp_path, capsys, change, expected):
    inp = copy.deepcopy(INPUT)
    change(inp)
    assert run(tmp_path, inp, checker_layout()) == EXIT_FILE_PROBLEM
    assert expected in capsys.readouterr().err


def test_unsuccessful_solver_result(tmp_path, capsys):
    result = {"status": "infeasible", "message": "rooms do not fit", "rooms": None}
    assert run(tmp_path, INPUT, result) == EXIT_FILE_PROBLEM
    assert "'infeasible'" in capsys.readouterr().err


def test_layout_index_out_of_range(tmp_path, capsys):
    assert run(tmp_path, INPUT, {"layouts": [checker_layout()]}, "--layout-index", "3") == EXIT_FILE_PROBLEM
    assert "does not exist" in capsys.readouterr().err


def test_file_problem_in_json_mode(tmp_path, capsys):
    assert run(tmp_path, INPUT, "[]", "--json") == EXIT_FILE_PROBLEM
    assert "file_problem" in json.loads(capsys.readouterr().out)


# --- Python use ---

def test_check_files_returns_the_problem_list(tmp_path):
    problems = check_files(write(tmp_path, "i.json", INPUT), write(tmp_path, "l.json", checker_layout()))
    assert problems == []


def test_check_files_passes_options_to_validate_all(tmp_path):
    layout = checker_layout()
    next(r for r in layout["rooms"] if r["name"] == "bathroom")["w"] -= 1
    paths = write(tmp_path, "i.json", INPUT), write(tmp_path, "l.json", layout)
    assert [p["code"] for p in check_files(*paths)] == ["H4"]
    assert check_files(*paths, check_gaps=False) == []


def test_check_files_raises_file_problem(tmp_path):
    with pytest.raises(FileProblem):
        check_files(str(tmp_path / "missing.json"), str(tmp_path / "missing.json"))
