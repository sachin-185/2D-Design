"""validate_file.py with plot coordinates (contract agreed with P1, 2026-11-11).

Plot coordinates put (0, 0) at the bottom-left of the whole plot; the checker works in buildable
coordinates. buildable = plot - (left setback, front setback). Front is always the bottom edge.
The setbacks below are all different, so mixing up left and right, or front and back, fails a test.
"""
import copy
import json
from pathlib import Path

import pytest

from validate_all import adapt_solver_result, validate_all
from validate_file import (
    EXIT_FILE_PROBLEM,
    EXIT_INVALID,
    EXIT_VALID,
    FileProblem,
    buildable_to_plot,
    check_files,
    choose_coordinate_system,
    main,
    plot_to_buildable,
    setback_offsets,
)

REGRESSION_DIR = Path(__file__).parent / "regression"

# The valid 30 x 24 buildable layout from test_validate_file.py, now with unequal setbacks around it.
SETBACKS = {"left": 4, "right": 1, "front": 6, "back": 2}
INPUT = {
    "plot": [30 + 4 + 1, 24 + 6 + 2],
    "setbacks": SETBACKS,
    "entrance": "S",
    "north": "up",
    "rooms": [
        {"name": "living", "type": "living"},
        {"name": "bedroom_1", "type": "bedroom"},
        {"name": "kitchen", "type": "kitchen"},
        {"name": "bathroom", "type": "bathroom"},
    ],
}


def buildable_layout():
    with open(REGRESSION_DIR / "latest_30x24_layout.json") as f:
        return adapt_solver_result(json.load(f))


def plot_layout():
    return buildable_to_plot(buildable_layout(), INPUT)


def write(folder, name, data):
    path = folder / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def run(folder, layout, *extra, inp=INPUT):
    return main([write(folder, "input.json", inp), write(folder, "layout.json", layout), *extra])


# --- the formula ---

def test_the_buildable_layout_is_valid_with_these_setbacks():
    assert [p for p in validate_all(INPUT, buildable_layout()) if p["severity"] == "error"] == []


def test_plot_position_adds_the_left_and_front_setbacks():
    first_b = buildable_layout()["rooms"][0]
    first_p = plot_layout()["rooms"][0]
    assert (first_p["x"], first_p["y"]) == (first_b["x"] + 4, first_b["y"] + 6)
    assert (first_p["w"], first_p["h"]) == (first_b["w"], first_b["h"])  # sizes never change


def test_round_trip_gives_back_exactly_the_same_layout():
    original = buildable_layout()
    assert plot_to_buildable(buildable_to_plot(original, INPUT), INPUT) == original


def test_doors_and_windows_move_too_including_fractions():
    layout = buildable_layout()
    layout["doors"] = [{"between": ["living", "hallway_1"], "x": 7.5, "y": 0.25}]
    layout["windows"] = [{"room": "living", "wall": "S", "x": 2.75, "y": 0}]
    plot = buildable_to_plot(layout, INPUT)
    assert plot["doors"][0]["x"] == pytest.approx(11.5) and plot["doors"][0]["y"] == pytest.approx(6.25)
    assert plot["windows"][0]["x"] == pytest.approx(6.75) and plot["windows"][0]["y"] == pytest.approx(6)
    back = plot_to_buildable(plot, INPUT)
    assert back["doors"][0]["x"] == pytest.approx(7.5) and back["doors"][0]["y"] == pytest.approx(0.25)
    assert back["doors"][0]["between"] == ["living", "hallway_1"]


def test_a_window_without_x_or_y_keeps_its_fields():
    layout = buildable_layout()
    layout["windows"] = [{"room": "living", "wall": "S"}]
    assert buildable_to_plot(layout, INPUT)["windows"] == [{"room": "living", "wall": "S"}]


def test_the_legacy_single_hallway_moves_too():
    layout = {"rooms": [], "hallway": {"x": 1, "y": 2, "w": 3, "h": 12}}
    assert buildable_to_plot(layout, INPUT)["hallway"] == {"x": 5, "y": 8, "w": 3, "h": 12}


def test_converting_does_not_change_the_original():
    layout = buildable_layout()
    before = copy.deepcopy(layout)
    buildable_to_plot(layout, INPUT)
    plot_to_buildable(layout, INPUT)
    assert layout == before


def test_checker_gives_the_same_problems_after_converting_back():
    original = buildable_layout()
    assert validate_all(INPUT, plot_to_buildable(plot_layout(), INPUT)) == validate_all(INPUT, original)


# --- setbacks ---

def test_missing_setbacks_count_as_zero():
    assert setback_offsets({"plot": [10, 10]}) == (0, 0)
    assert setback_offsets({"setbacks": {"back": 3}}) == (0, 0)


@pytest.mark.parametrize("value", [None, -1, 1.5, "2"])
def test_a_bad_setback_value_is_a_file_problem(value):
    with pytest.raises(FileProblem, match="setback"):
        setback_offsets({"setbacks": {"left": value}})


# --- which coordinate system is used ---

@pytest.mark.parametrize("option, marker, expected", [
    ("plot", "buildable", ("plot", "--coords option")),
    ("buildable", "plot", ("buildable", "--coords option")),
    (None, "plot", ("plot", "'coordinate_system' in the file")),
    (None, None, ("buildable", "default")),
])
def test_option_then_marker_then_buildable(option, marker, expected):
    assert choose_coordinate_system(option, marker) == expected


def test_an_unknown_marker_is_a_file_problem():
    with pytest.raises(FileProblem, match="coordinate system"):
        choose_coordinate_system(None, "metres")


# --- the command ---

def test_plot_file_with_the_option_is_valid(tmp_path, capsys):
    assert run(tmp_path, plot_layout(), "--coords", "plot") == EXIT_VALID
    out = capsys.readouterr().out
    assert "Coordinates: plot (from the --coords option)" in out and "Result: VALID" in out


def test_plot_file_read_as_buildable_fails_on_purpose(tmp_path):
    """Without the option or a marker the file is taken as buildable, so every room looks shifted."""
    assert run(tmp_path, plot_layout()) == EXIT_INVALID


def test_marker_at_the_top_of_an_api_response_is_used(tmp_path):
    response = {"layouts": [plot_layout()], "coordinate_system": "plot"}
    assert run(tmp_path, response) == EXIT_VALID


def test_marker_inside_the_chosen_layout_is_used(tmp_path):
    response = {"layouts": [buildable_layout(), {**plot_layout(), "coordinate_system": "plot"}]}
    assert run(tmp_path, response, "--layout-index", "1") == EXIT_VALID


def test_option_overrides_the_marker(tmp_path):
    marked_wrongly = {"layouts": [buildable_layout()], "coordinate_system": "plot"}
    assert run(tmp_path, marked_wrongly) == EXIT_INVALID
    assert run(tmp_path, marked_wrongly, "--coords", "buildable") == EXIT_VALID


def test_buildable_files_keep_working_without_any_option(tmp_path, capsys):
    assert run(tmp_path, buildable_layout()) == EXIT_VALID
    assert "Coordinates: buildable (from the default)" in capsys.readouterr().out


def test_an_unknown_marker_in_a_file_exits_with_a_file_problem(tmp_path):
    assert run(tmp_path, {**plot_layout(), "coordinate_system": "metres"}) == EXIT_FILE_PROBLEM


def test_a_room_inside_the_setback_is_still_an_error(tmp_path, capsys):
    """Setbacks stay enforced: a room 1 ft into the left setback is outside the buildable area (H1)."""
    layout = plot_layout()
    layout["rooms"][0]["x"] = 3  # left setback is 4
    assert run(tmp_path, layout, "--coords", "plot") == EXIT_INVALID
    assert "[H1]" in capsys.readouterr().out


def test_json_report_says_which_coordinates_were_used(tmp_path, capsys):
    run(tmp_path, plot_layout(), "--coords", "plot", "--json")
    report = json.loads(capsys.readouterr().out)
    assert report["valid"] is True
    assert report["coordinate_system"] == "plot" and report["coordinate_source"] == "--coords option"


def test_no_setbacks_object_or_null_means_all_zero(tmp_path):
    """P1's point 1: a missing or null setbacks object means all setbacks are 0, so plot == buildable."""
    for setbacks in ("missing", None):
        inp = {k: v for k, v in INPUT.items() if k != "setbacks"}
        inp["plot"] = [30, 24]
        if setbacks is None:
            inp["setbacks"] = None
        assert setback_offsets(inp) == (0, 0)
        assert buildable_to_plot(buildable_layout(), inp) == buildable_layout()
        assert run(tmp_path, buildable_layout(), "--coords", "plot", inp=inp) == EXIT_VALID


def with_doors_and_windows(doors=None, windows=None):
    layout = plot_layout()
    if doors is not None:
        layout["doors"] = doors
    if windows is not None:
        layout["windows"] = windows
    return layout


@pytest.mark.parametrize("doors, message", [
    ([{"between": ["living", "hallway_1"], "x": 7.5}], "door 1 (living / hallway_1) needs a number 'y'"),
    ([{"between": ["living", "hallway_1"], "x": "7", "y": 1}], "door 1 (living / hallway_1) needs a number 'x'"),
    ([{"between": ["a", "b"], "x": 1, "y": None}], "door 1 (a / b) needs a number 'y'"),
    ([{"between": ["a", "b"], "x": True, "y": 1}], "door 1 (a / b) needs a number 'x'"),
    (["not an object"], "door 1 must be a JSON object"),
    ({"x": 1, "y": 1}, "'doors' must be a list"),
])
def test_bad_doors_are_a_file_problem_naming_the_door_and_field(tmp_path, capsys, doors, message):
    """P1's points 2 and 3: a door with a missing or invalid position is reported, never left unshifted."""
    assert run(tmp_path, with_doors_and_windows(doors=doors), "--coords", "plot") == EXIT_FILE_PROBLEM
    assert message in capsys.readouterr().err


@pytest.mark.parametrize("windows, message", [
    ([{"room": "living", "wall": "S"}], "window 1 (living, S wall) needs a number 'x'"),
    ([{"room": "living", "wall": "S", "x": 2, "y": None}], "window 1 (living, S wall) has 'y' None"),
    ([{"room": "living", "wall": "S", "x": 2, "y": "top"}], "window 1 (living, S wall) has 'y' 'top'"),
    ("none", "'windows' must be a list"),
])
def test_bad_windows_are_a_file_problem_naming_the_window_and_field(tmp_path, capsys, windows, message):
    assert run(tmp_path, with_doors_and_windows(windows=windows), "--coords", "plot") == EXIT_FILE_PROBLEM
    assert message in capsys.readouterr().err


def test_good_doors_and_windows_are_accepted_and_checked_in_buildable_too(tmp_path):
    doors = [{"between": ["living", "outside"], "x": 9.5, "y": 6}]
    windows = [{"room": "living", "wall": "S", "x": 6.75}, {"room": "kitchen", "wall": "E", "x": 34, "y": 8.5}]
    assert run(tmp_path, with_doors_and_windows(doors, windows), "--coords", "plot") == EXIT_VALID
    assert run(tmp_path, {**buildable_layout(), "doors": [{"between": ["a", "b"], "x": 1}]}) == EXIT_FILE_PROBLEM


def test_null_or_missing_door_and_window_lists_mean_none(tmp_path):
    assert run(tmp_path, {**plot_layout(), "doors": None, "windows": None}, "--coords", "plot") == EXIT_VALID


def test_check_files_accepts_the_option(tmp_path):
    inp, layout = write(tmp_path, "input.json", INPUT), write(tmp_path, "layout.json", plot_layout())
    errors = [p for p in check_files(inp, layout, coords="plot") if p["severity"] == "error"]
    assert errors == []
