"""End-to-end checks against the teammates' REAL modules.

Each test runs only when the module it needs is in the repo (and ortools is installed
for the solver tests); otherwise it is skipped, not failed. Run from the project root:
    python -m pytest tests -q -rs        (-rs lists what was skipped and why)
"""
import copy

import pytest

from floorplan.config import get_checker_size_table
from floorplan.runner import execute_engine_request, execute_pipeline
from floorplan.schema import FloorPlanInput, FloorPlanOutput
from tests import fakes

SAMPLE = {
    "plot": [40, 50],
    "setbacks": {"front": 5, "back": 5, "left": 3, "right": 3},
    "entrance": "S",
    "north": "up",
    "rooms": [
        {"name": "Living", "type": "living"},
        {"name": "Kitchen", "type": "kitchen"},
        {"name": "Bedroom", "type": "bedroom"},
        {"name": "Bath", "type": "bathroom", "attached_to": "Bedroom"},
    ],
}


def payload():
    return FloorPlanInput.model_validate(copy.deepcopy(SAMPLE)).model_dump(exclude_none=True)


def p4_checker():
    validator = pytest.importorskip("floorplan.validator", reason="P4 floorplan/validator.py not in repo")

    def check(inp, layout):
        return validator.validate(inp, layout, size_table=get_checker_size_table(inp["rooms"]))
    return check


# ------------------------------------------------- pure-Python modules ---
def test_p4_check_input_accepts_p3_input():
    validator = pytest.importorskip("floorplan.validator")
    assert validator.check_input(payload()) == []


def test_p4_validator_passes_a_clean_p3_layout_and_catches_overlap():
    check = p4_checker()
    out = execute_pipeline(FloorPlanInput.model_validate(SAMPLE),
                           solver_func=fakes.fake_solve_layout, checker_func=check)
    assert isinstance(out, FloorPlanOutput), out

    def overlapping(**kw):
        res = fakes.fake_solve_layout(**kw)
        res["rooms"]["Kitchen"] = dict(res["rooms"]["Living"])
        return res
    bad = execute_pipeline(FloorPlanInput.model_validate(SAMPLE),
                           solver_func=overlapping, checker_func=check)
    assert bad.error_code == "VALIDATION_FAILED"
    assert any("overlap" in e for e in bad.details["errors"])


def test_connections_required_pairs_reads_p3_input():
    connections = pytest.importorskip("floorplan.connections")
    pairs = connections.required_pairs(payload())
    assert ("Bath", "Bedroom") in pairs and ("Kitchen", "Living") in pairs


def test_input_adapter_accepts_p3_input():
    adapter = pytest.importorskip("floorplan.input_adapter")
    inp = FloorPlanInput.model_validate({**SAMPLE, "pins": [{"room": "Bedroom", "width": 12}]})
    data = inp.model_dump(exclude_none=True)
    args = adapter.build_preference_arguments(data, get_checker_size_table(data["rooms"]))
    assert set(args["setbacks"]) == {"left", "right", "front", "back"}
    assert args["pinned_dimensions"] == {"Bedroom": {"width": 12}}
    assert args["entrance_room"] == "Living"


# ---------------------------------------------- solver (needs ortools) ---
def test_real_p1_solver_through_p3_pipeline():
    pytest.importorskip("ortools", reason="ortools not installed (use Python 3.12)")
    geometry = pytest.importorskip("floorplan.geometry", reason="P1 floorplan/geometry.py not in repo")
    out = execute_pipeline(FloorPlanInput.model_validate(SAMPLE),
                           solver_func=geometry.solve_layout, checker_func=p4_checker())
    assert isinstance(out, FloorPlanOutput), out.model_dump()
    layout = out.layouts[0]
    assert {r.name for r in layout.rooms} == {"Living", "Kitchen", "Bedroom", "Bath"}
    assert layout.hallway_segments, "expected at least one hallway segment"
    assert sum(max(s.w, s.h) for s in layout.hallway_segments) >= 12


def test_real_engine_through_p3():
    pytest.importorskip("ortools", reason="ortools not installed (use Python 3.12)")
    pytest.importorskip("validate_all", reason="P4 validate_all.py not in repo root")
    engine = pytest.importorskip("floorplan.engine", reason="P2 floorplan/engine.py not in repo")
    out = execute_engine_request(FloorPlanInput.model_validate(SAMPLE), engine.solve_request)
    assert isinstance(out, FloorPlanOutput), out.model_dump()
    assert 1 <= len(out.layouts) <= 3
