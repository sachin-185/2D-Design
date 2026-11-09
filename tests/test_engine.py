"""The whole engine, end to end: P3 config -> P1 + P2 solve -> P4 checker -> output JSON."""
import json
from pathlib import Path

import pytest

from floorplan.engine import OUTSIDE, edit_layout, shared_wall, solve_request
from floorplan.input_adapter import build_preferred_adjacencies
from floorplan.preferences import (
    calculate_zone_bounds,
    generate_variants,
    is_near_duplicate,
    solve_with_preferences,
    to_drawing_side,
    to_drawing_zone,
)
from floorplan.schema import FloorPlanOutput
from validate_all import validate_all

FOLDER = Path(__file__).parent / "TestCases"
SECONDS = 5


def load(name):
    return json.load(open(FOLDER / f"{name}.json"))["input"]


@pytest.fixture(scope="module")
def t01():
    return solve_request(load("t01_standard"), time_limit_seconds=SECONDS)


def room(layout, name):
    return next(r for r in layout["rooms"] if r["name"] == name)


# --- whole inputs ---------------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "t01_standard", "t02_tight", "t09_rotated", "t10_pinned", "t11_attached_bathroom",
    "t14_entrance_north", "t15_east_north_left", "t16_large_setbacks", "t17_two_living_rooms",
    "t21_east_entrance", "t23_north_down", "t24_dining_utility",
])
def test_valid_inputs_give_layouts_that_pass_the_independent_checker(name):
    inp = load(name)
    result = solve_request(inp, time_limit_seconds=SECONDS)
    assert result["status"] == "valid", result["messages"]
    assert result["layouts"]
    for layout in result["layouts"]:
        problems = validate_all(inp, layout, size_table=_table(inp))
        assert [p for p in problems if p.get("severity", "error") == "error"] == []


def _table(inp):
    from floorplan.engine import room_size_table
    return room_size_table(inp)


@pytest.mark.parametrize("name", ["t03_too_small", "t06_too_many", "t20_no_arrangement"])
def test_inputs_that_cannot_fit_are_infeasible_with_a_reason(name):
    result = solve_request(load(name), time_limit_seconds=SECONDS)
    assert result["status"] == "infeasible"
    assert result["layouts"] == [] and result["messages"]


def test_too_small_says_by_how_much():
    message = solve_request(load("t03_too_small"))["messages"][0]
    assert "Short by 229 sq ft" in message


def test_plot_much_too_large_is_reported_instead_of_drawn():
    result = solve_request(load("t07_plot_too_large"))
    assert result["status"] == "infeasible"
    assert "Plot too large" in result["messages"][0] and "3888" in result["messages"][0]


def test_output_fits_p3_schema(t01):
    FloorPlanOutput(layouts=t01["layouts"])


def test_bad_input_is_reported_not_solved():
    result = solve_request({"plot": [30, 40], "entrance": "Q", "rooms": [{"name": "living", "type": "living"}]})
    assert result["status"] == "invalid" and result["messages"]


def test_no_living_room_is_a_clear_error():
    result = solve_request({"plot": [30, 40], "entrance": "S", "rooms": [{"name": "bed", "type": "bedroom"}]})
    assert result["status"] == "invalid" and "living room" in result["messages"][0]


# --- variants -------------------------------------------------------------------------------------

def test_three_different_layouts_best_score_first(t01):
    layouts = t01["layouts"]
    assert len(layouts) == 3
    assert [l["score"] for l in layouts] == sorted(l["score"] for l in layouts)
    assert len({l["archetype"] for l in layouts}) == 3


def test_each_layout_moves_at_least_two_rooms_to_another_zone():
    inp = load("t01_standard")
    from floorplan.engine import preferred_sizes, room_size_table
    from floorplan.input_adapter import build_preference_arguments
    args = build_preference_arguments(inp, room_size_table(inp), preferred_sizes(inp))
    variants = generate_variants(count=2, time_limit_seconds=SECONDS, **args)
    first, second = variants[0]["room_zones"], variants[1]["room_zones"]
    assert sum(first[name] != second[name] for name in first) >= 2


def test_near_duplicates_are_recognised():
    a = {"r": {"x": 0, "y": 0, "width": 10, "height": 10}}
    assert is_near_duplicate(a, {"r": {"x": 2, "y": 1, "width": 10, "height": 11}})
    assert not is_near_duplicate(a, {"r": {"x": 3, "y": 0, "width": 10, "height": 10}})


def test_central_hallway_is_a_full_length_spine_with_room_on_both_sides(t01):
    layout = next(l for l in t01["layouts"] if l["archetype"] == "central_hallway")
    hall = layout["hallway_segments"][0]
    W, L = 24, 32
    if hall["w"] <= 4:
        assert hall["h"] == L and hall["x"] >= 1 and hall["x"] + hall["w"] <= W - 1
    else:
        assert hall["w"] == W and hall["y"] >= 1 and hall["y"] + hall["h"] <= L - 1


# --- zones and north ------------------------------------------------------------------------------

def test_real_world_sides_turn_with_north():
    assert to_drawing_side("N", "left") == "W"
    assert to_drawing_side("S", "up") == "S"
    assert to_drawing_zone("NW", "left") == "SW"
    assert to_drawing_zone("SE", "right") == "SW"
    assert to_drawing_zone("Mid", "down") == "Mid"


def test_must_zone_holds_on_a_turned_plot():
    result = solve_request(load("t09_rotated"), time_limit_seconds=SECONDS)  # north left, bedroom must be NW
    assert result["status"] == "valid"
    zone = calculate_zone_bounds(24, 32, "SW")  # real NW is the drawing's bottom-left
    for layout in result["layouts"]:
        bedroom = room(layout, "bedroom")
        assert 2 * zone["x_min"] <= 2 * bedroom["x"] + bedroom["w"] <= 2 * zone["x_max"]
        assert 2 * zone["y_min"] <= 2 * bedroom["y"] + bedroom["h"] <= 2 * zone["y_max"]
        assert room(layout, "living")["x"] == 0  # entrance N is the drawing's left edge


def test_impossible_must_zone_is_a_conflict_naming_the_room():
    result = solve_request(load("t08_conflicting_musts"), time_limit_seconds=SECONDS)
    # living must touch the south wall, so its center can never be in NW
    assert result["status"] == "conflict" and result["conflict_rooms"] == ["living"]
    assert "living in NW" in result["messages"][0]


def test_two_rooms_competing_for_one_zone_are_both_named():
    inp = load("t01_standard")
    inp = {**inp, "rooms": [
        {"name": "living", "type": "living"},
        {"name": "kitchen", "type": "kitchen"},
        {"name": "bed1", "type": "bedroom", "zone": "NW", "zone_mode": "must"},
        {"name": "bed2", "type": "bedroom", "zone": "NW", "zone_mode": "must"},
    ]}
    result = solve_request(inp, time_limit_seconds=SECONDS)
    assert result["status"] == "conflict" and sorted(result["conflict_rooms"]) == ["bed1", "bed2"]


def test_missed_try_zone_is_reported():
    inp = load("t01_standard")
    inp = {**inp, "rooms": [
        {"name": "living", "type": "living", "zone": "S", "zone_mode": "must"},
        {"name": "kitchen", "type": "kitchen", "zone": "NE", "zone_mode": "try"},
        {"name": "bedroom", "type": "bedroom", "zone": "SW", "zone_mode": "try"},
        {"name": "bathroom", "type": "bathroom", "zone": "SE", "zone_mode": "try"},
    ]}
    result = solve_request(inp, time_limit_seconds=SECONDS)
    assert result["status"] == "valid"
    assert any("preference relaxed" in m for l in result["layouts"] for m in l["messages"])


# --- scoring --------------------------------------------------------------------------------------

def test_score_is_the_sum_of_the_named_penalties(t01):
    for layout in t01["layouts"]:
        assert layout["score"] == sum(layout["penalties"].values())
        assert {"S1_preferred_sizes", "S3_hallway_area", "S4_adjacency_quality", "unused_area"} <= set(layout["penalties"])


def test_gap_penalty_fills_the_plot(t01):
    assert max(l["coverage_percent"] for l in t01["layouts"]) >= 90


def test_preferred_adjacency_pulls_rooms_together():
    specs = {
        "a": {"min_width": 6, "max_width": 6, "min_height": 6, "max_height": 6},
        "b": {"min_width": 6, "max_width": 6, "min_height": 6, "max_height": 6},
    }
    res = solve_with_preferences(plot_width=40, plot_height=40, room_specs=specs, entrance=None,
                                 preferred_adjacencies=[("a", "b")])
    assert res["status"] == "success" and res["penalties"]["S4_adjacency_quality"] == 0


def test_bathrooms_should_be_near_bedrooms_but_ensuites_need_no_rule():
    inp = {"rooms": [
        {"name": "bed", "type": "bedroom"},
        {"name": "common", "type": "bathroom"},
        {"name": "ensuite", "type": "bathroom", "attached_to": "bed"},
    ]}
    assert build_preferred_adjacencies(inp) == [("common", "bed")]


def test_wall_shorter_than_a_door_does_not_count():
    # A 2 x 2 ft room can never share 3 ft of wall.
    res = solve_with_preferences(plot_width=20, plot_height=20, room_specs={
        "tiny": {"min_width": 2, "max_width": 2, "min_height": 2, "max_height": 2},
        "big": {"min_width": 8, "max_width": 8, "min_height": 8, "max_height": 8},
    }, required_adjacencies=[("tiny", "big")])
    assert res["status"] == "infeasible"


def test_unknown_room_in_an_adjacency_is_an_error_not_ignored():
    with pytest.raises(ValueError, match="unknown room 'ghost'"):
        solve_with_preferences(plot_width=20, plot_height=20, room_specs={
            "a": {"min_width": 6, "max_width": 8, "min_height": 6, "max_height": 8},
        }, required_adjacencies=[("a", "ghost")])


# --- small plots with no hallway ------------------------------------------------------------------

def test_small_plot_falls_back_to_no_hallway():
    inp = load("t19_small_no_hallway")
    result = solve_request(inp, time_limit_seconds=SECONDS)
    assert result["status"] == "valid"
    for layout in result["layouts"]:
        assert layout["hallway_segments"] == []
        assert any("no hallway" in m for m in layout["messages"])


# --- doors ----------------------------------------------------------------------------------------

def test_every_room_has_a_door_on_a_real_shared_wall(t01):
    for layout in t01["layouts"]:
        boxes = {r["name"]: r for r in layout["rooms"]}
        boxes.update({h["id"]: h for h in layout["hallway_segments"]})
        with_door = set()
        for door in layout["doors"]:
            a, b = door["between"]
            with_door.update((a, b))
            if a == OUTSIDE:
                continue
            (x1, y1), (x2, y2) = shared_wall(boxes[a], boxes[b])
            assert x1 <= door["x"] <= x2 and y1 <= door["y"] <= y2
        assert set(room_["name"] for room_ in layout["rooms"]) <= with_door


def test_main_door_is_on_the_entrance_wall(t01):
    for layout in t01["layouts"]:
        main = next(d for d in layout["doors"] if d["between"][0] == OUTSIDE)
        assert main["between"][1] == "living" and main["y"] == 0  # entrance S with north up


def test_reachability_only_rooms_are_connected():
    result = solve_request(load("t24_dining_utility"), time_limit_seconds=SECONDS)
    assert result["status"] == "valid"
    for layout in result["layouts"]:
        names = {name for door in layout["doors"] for name in door["between"]}
        assert {"dining", "utility"} <= names


def test_output_keeps_the_users_room_type():
    result = solve_request(load("t24_dining_utility"), time_limit_seconds=SECONDS)
    types = {r["name"]: r["type"] for r in load("t24_dining_utility")["rooms"]}
    for layout in result["layouts"]:
        assert {r["name"]: r["type"] for r in layout["rooms"]} == types


# --- edit and re-solve ----------------------------------------------------------------------------

def test_edit_pins_the_size_and_locks_the_accepted_room(t01):
    inp = load("t01_standard")
    layout = t01["layouts"][0]
    before = room(layout, "living")
    wanted = 12 if room(layout, "bedroom")["w"] != 12 else 11
    result = edit_layout(inp, layout, {"bedroom": {"width": wanted}}, lock=["living"], time_limit_seconds=SECONDS)
    assert result["status"] == "valid", result["messages"]
    assert len(result["layouts"]) == 1
    edited = result["layouts"][0]
    assert room(edited, "bedroom")["w"] == wanted
    assert room(edited, "living") == before
    assert {"room": "bedroom", "width": wanted} in result["input"]["pins"]
    assert validate_all(result["input"], edited, size_table=_table(inp)) == [] or all(
        p["severity"] == "warning" for p in validate_all(result["input"], edited, size_table=_table(inp)))


def test_a_locked_pin_stays_put_and_the_lock_carries_to_the_next_edit(t01):
    inp = {**load("t01_standard"), "pins": [{"room": "living", "locked": True}]}
    layout = t01["layouts"][0]
    before = room(layout, "living")
    wanted = 12 if room(layout, "bedroom")["w"] != 12 else 11
    first = edit_layout(inp, layout, {"bedroom": {"width": wanted}}, time_limit_seconds=SECONDS)
    assert first["status"] == "valid", first["messages"]
    assert room(first["layouts"][0], "living") == before
    assert {"room": "living", "locked": True} in first["input"]["pins"]

    # editing a locked room unlocks it
    second = edit_layout(first["input"], first["layouts"][0], {"living": {"width": before["w"]}},
                         time_limit_seconds=SECONDS)
    assert "living was edited, so it was unlocked." in second["messages"]
    assert all(not p.get("locked") for p in second["input"]["pins"] if p["room"] == "living")


def test_edit_moves_other_rooms_as_little_as_possible(t01):
    inp = load("t01_standard")
    layout = t01["layouts"][0]
    wanted = 12 if room(layout, "bedroom")["h"] != 12 else 11
    edited = edit_layout(inp, layout, {"bedroom": {"height": wanted}}, time_limit_seconds=SECONDS)
    assert edited["status"] == "valid", edited["messages"]
    assert "S6_minimal_change" in edited["layouts"][0]["penalties"]


def test_impossible_edit_gives_the_reason_and_the_nearest_value_that_works(t01):
    inp = load("t01_standard")
    result = edit_layout(inp, t01["layouts"][0], {"bedroom": {"width": 40}}, time_limit_seconds=SECONDS)
    assert result["status"] == "infeasible" and result["layouts"] == []
    assert result["nearest"]["bedroom"]["width"] == 16  # the size table's maximum
    assert "Nearest bedroom width that works: 16 ft" in result["messages"][0]


def test_editing_an_unknown_room_is_an_error(t01):
    result = edit_layout(load("t01_standard"), t01["layouts"][0], {"ghost": {"width": 12}})
    assert result["status"] == "invalid" and "ghost" in result["messages"][0]
