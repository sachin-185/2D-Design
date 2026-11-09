"""P3 tests: python -m pytest tests -q"""
import copy

import pytest
from pydantic import ValidationError

from floorplan.runner import (
    build_solver_kwargs,
    check_feasibility,
    execute_engine_request,
    execute_pipeline,
    split_checker_problems,
)
from floorplan.schema import ErrorResponse, FloorPlanInput, FloorPlanOutput
from tests import fakes

BASE = {
    "plot": [40, 50],
    "setbacks": {"front": 5, "back": 5, "left": 3, "right": 3},
    "rooms": [
        {"name": "Living", "type": "living"},
        {"name": "Kitchen", "type": "kitchen"},
        {"name": "Bedroom", "type": "bedroom"},
        {"name": "Bath", "type": "bathroom", "attached_to": "Bedroom"},
        {"name": "Dining", "type": "dining"},
    ],
}


def inp(**overrides):
    data = copy.deepcopy(BASE)
    data.update(overrides)
    return FloorPlanInput.model_validate(data)


def run(i=None, **kw):
    kw.setdefault("solver_func", fakes.fake_solve_layout)
    return execute_pipeline(i or inp(), **kw)


# ---------------------------------------------------------------- schema ---
def test_names_are_stripped_so_duplicates_are_caught():
    rooms = [{"name": "Living", "type": "living"}, {"name": " Living ", "type": "kitchen"}]
    with pytest.raises(ValidationError, match="Duplicate room name"):
        inp(rooms=rooms)


def test_attached_to_is_stripped():
    rooms = [{"name": "Living", "type": "living"}, {"name": "Bed", "type": "bedroom"},
             {"name": "Bath", "type": "bathroom", "attached_to": " Bed"}]
    assert inp(rooms=rooms).rooms[2].attached_to == "Bed"


def test_duplicate_pins_rejected():
    with pytest.raises(ValidationError, match="pinned more than once"):
        inp(pins=[{"room": "Living", "width": 14}, {"room": "Living", "height": 14}])


# ----------------------------------------------------------- feasibility ---
def test_room_wider_than_plot():
    err = check_feasibility(inp(plot=[16, 60], setbacks={"left": 3, "right": 3}))
    assert err.error_code == "ROOM_DOES_NOT_FIT" and err.details["room"] == "Living"


def test_area_exceeded():
    err = check_feasibility(inp(plot=[20, 20], setbacks={}))
    assert err.error_code == "INFEASIBLE_AREA"


def test_hallway_minimum_counts_for_small_inputs():
    # living 144 + 15% = 165 fits 13x13=169, but a 3x12 hallway (36) makes it 180.
    i = inp(plot=[13, 13], setbacks={}, rooms=[{"name": "Living", "type": "living"}])
    assert check_feasibility(i).error_code == "INFEASIBLE_AREA"


def test_feasible_input_passes():
    assert check_feasibility(inp()) is None


# ------------------------------------------------------- P1 boundary ---
def test_solver_kwargs_filtered_to_signature():
    kw = build_solver_kwargs(inp(), fakes.solver_without_layout_input)
    assert "layout_input" not in kw and "max_hallway_segments" not in kw
    out = run(solver_func=fakes.solver_without_layout_input)
    assert isinstance(out, FloorPlanOutput)


def test_success_keeps_original_types_and_float_score():
    out = run(checker_func=fakes.validate_all)
    assert isinstance(out, FloorPlanOutput), out
    layout = out.layouts[0]
    assert {r.name: r.type for r in layout.rooms}["Dining"] == "dining"
    assert layout.score == 87.5
    assert layout.messages == ["Warning: Kitchen far from dining", "Warning: Score computed"]


def test_solver_timeout():
    out = run(solver_func=fakes.slow_solver, hard_timeout_seconds=0.5)
    assert isinstance(out, ErrorResponse)
    assert (out.status, out.error_code) == ("timeout", "SOLVER_TIMEOUT")


def test_solver_exception():
    assert run(solver_func=fakes.crashing_solver).error_code == "SOLVER_EXCEPTION"


def test_p1_unknown_status_is_a_timeout():
    # geometry.solve_layout returns "unknown" when CP-SAT hits its time limit.
    out = run(solver_func=lambda **k: {"status": "unknown", "message": "time limit", "rooms": None})
    assert (out.status, out.error_code) == ("timeout", "SOLVER_TIMEOUT")


def test_p1_is_asked_to_be_quiet():
    assert build_solver_kwargs(inp(), fakes.fake_solve_layout)["verbose"] is False


def test_unexpected_solver_status_does_not_crash():
    out = run(solver_func=lambda **k: {"status": "model_invalid"})
    assert isinstance(out, ErrorResponse) and out.status == "error" and out.error_code == "SOLVER_FAILED"


def test_solver_missing_room():
    def drops_one(**k):
        res = fakes.fake_solve_layout(**k)
        res["rooms"].pop("Kitchen")
        return res
    out = run(solver_func=drops_one)
    assert out.error_code == "INVALID_SOLVER_RESULT" and out.details["missing_rooms"] == ["Kitchen"]


def test_solver_rooms_as_list():
    def as_list(**k):
        res = fakes.fake_solve_layout(**k)
        res["rooms"] = [{"name": n, "x": v["x"], "y": v["y"], "width": v["w"], "height": v["h"]}
                        for n, v in res["rooms"].items()]
        return res
    assert isinstance(run(solver_func=as_list), FloorPlanOutput)


def test_no_solver():
    assert execute_pipeline(inp()).error_code == "NO_SOLVER_AVAILABLE"


def test_dict_input_with_errors_returns_error_not_exception():
    out = execute_pipeline({"plot": [40, 50], "rooms": [{"name": "K", "type": "kitchen"}]},
                           solver_func=fakes.fake_solve_layout)
    assert isinstance(out, ErrorResponse) and out.error_code == "INVALID_INPUT"


# ------------------------------------------------------------- P4 checker ---
def test_info_severity_is_a_warning_not_an_error():
    errors, warnings = split_checker_problems([{"severity": "info", "message": "fyi"}])
    assert errors == [] and warnings == ["fyi"]


def test_checker_hard_errors_return_layout_for_p5():
    out = run(checker_func=fakes.validate_all_failing)
    assert out.error_code == "VALIDATION_FAILED"
    assert out.details["errors"] == ["Rooms overlap"]
    assert out.details["warnings"] == ["Small window"]
    assert len(out.details["layout"]["rooms"]) == 5


def test_errors_only_path_returns_messages():
    out = run(checker_func=fakes.validate_all_failing, errors_only_func=fakes.errors_only)
    assert out.details["errors"] == ["Rooms overlap"] and out.details["warnings"] == ["Small window"]


def test_errors_only_with_dict_result_does_not_break():
    out = run(checker_func=fakes.checker_returning_dict, errors_only_func=lambda r: [])
    assert isinstance(out, FloorPlanOutput)
    assert out.layouts[0].messages == ["Warning: Bathroom has no window"]


def test_checker_crash():
    def boom(p, l):
        raise KeyError("rooms")
    assert run(checker_func=boom).error_code == "CHECKER_CRASHED"


# ----------------------------------------------------------------- engine ---
from floorplan.runner import execute_engine_edit  # noqa: E402


def test_engine_valid_keeps_extras_and_messages():
    out = execute_engine_request(inp(), fakes.engine_ok)
    assert isinstance(out, FloorPlanOutput), out
    layout = out.model_dump()["layouts"][0]
    assert layout["score"] == 91.25
    assert layout["archetype"] == "linear" and layout["coverage_percent"] == 64.3
    assert layout["doors"][0]["between"] == ["outside", "Living"]
    assert out.messages[0].startswith("Dropped a layout")


def test_engine_failure_with_dict_messages():
    out = execute_engine_request(inp(), lambda p: {"status": "conflict", "layouts": [],
                                                   "conflict_rooms": ["Bedroom"],
                                                   "messages": [{"message": "Zone clash"}, "Pin too big"]})
    assert out.status == "conflict" and out.error_code == "CONFLICT"
    assert out.message == "Zone clash; Pin too big" and out.details["conflict_rooms"] == ["Bedroom"]


def test_engine_invalid_status():
    out = execute_engine_request(inp(), lambda p: {"status": "invalid", "layouts": [],
                                                   "messages": ["Room too small"]})
    assert (out.status, out.error_code) == ("invalid", "INVALID")


def test_engine_bad_output():
    out = execute_engine_request(inp(), lambda p: {"status": "valid", "layouts": [{"rooms": "nope"}]})
    assert out.error_code == "INVALID_ENGINE_RESULT"


def test_engine_timeout():
    def slow(p):
        import time
        time.sleep(3)
    assert execute_engine_request(inp(), slow, hard_timeout_seconds=0.5).error_code == "SOLVER_TIMEOUT"


def test_engine_path_leaves_area_check_to_engine():
    # Small plot: P3's hallway minimum would reject it, but the engine may build a no-hallway plan.
    small = inp(plot=[13, 13], setbacks={}, rooms=[{"name": "Living", "type": "living"}])
    assert check_feasibility(small) is not None
    seen = []
    execute_engine_request(small, lambda p: seen.append(p) or {"status": "infeasible", "messages": ["x"]})
    assert seen, "engine must be called"


def _edit_body(**over):
    first = execute_engine_request(inp(), fakes.engine_ok)
    body = {"input": BASE, "layout": first.model_dump()["layouts"][0],
            "edits": {"Bedroom": {"width": 14}}, "lock": ["Living"]}
    body.update(over)
    return body


def test_engine_edit_success_returns_updated_input():
    out = execute_engine_edit(_edit_body(), fakes.engine_edit_ok)
    assert isinstance(out, FloorPlanOutput), out
    assert out.input["pins"] == [{"room": "Bedroom", "width": 14}]
    # the returned input is valid to send straight back for the next edit
    FloorPlanInput.model_validate(out.input)


def test_engine_edit_infeasible_returns_nearest():
    out = execute_engine_edit(_edit_body(edits={"Bedroom": {"width": 16}}), fakes.engine_edit_infeasible)
    assert out.error_code == "INFEASIBLE" and out.details["nearest"] == {"Bedroom": {"width": 13}}


def test_engine_edit_rejects_unknown_room_and_bad_size():
    assert execute_engine_edit(_edit_body(edits={"Garage": {"width": 10}}),
                               fakes.engine_edit_ok).error_code == "INVALID_INPUT"
    assert execute_engine_edit(_edit_body(edits={"Bedroom": {"width": 0}}),
                               fakes.engine_edit_ok).error_code == "INVALID_INPUT"
    assert execute_engine_edit(_edit_body(edits={"Bedroom": {"depth": 12}}),
                               fakes.engine_edit_ok).error_code == "INVALID_INPUT"
