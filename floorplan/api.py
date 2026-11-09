"""
floorplan/api.py
FastAPI web server connecting P5 UI to engine.py (or runner.py fallback).
Owner: P3 (Input and Glue)

Error contract for P5 (unchanged): every failure is HTTP 400 with body
    {"detail": {"status", "error_code", "message", "details"}}
"""

import logging

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

try:
    from floorplan.schema import FloorPlanInput, FloorPlanOutput, ErrorResponse, EditLayoutRequest
    from floorplan.runner import execute_pipeline, execute_engine_request, execute_engine_edit
except ModuleNotFoundError:
    from schema import FloorPlanInput, FloorPlanOutput, ErrorResponse, EditLayoutRequest
    from runner import execute_pipeline, execute_engine_request, execute_engine_edit

log = logging.getLogger("floorplan.api")

# Why each optional teammate module failed to import, shown by /health.
# A module that exists but has a broken dependency (e.g. ortools missing) is
# otherwise indistinguishable from a module that is simply not there.
IMPORT_ERRORS: dict = {}


def _note(component: str, exc: Exception) -> None:
    IMPORT_ERRORS.setdefault(component, []).append(f"{type(exc).__name__}: {exc}")


# Check if P2/P4 engine is available
try:
    from floorplan.engine import solve_request, edit_layout
except ImportError as e:
    _note("engine", e)
    try:
        from engine import solve_request, edit_layout
    except ImportError as e2:
        _note("engine", e2)
        solve_request, edit_layout = None, None

# Fallback imports if engine is not present
try:
    from geometry import solve_layout
except ImportError as e:
    _note("solver", e)
    try:
        from floorplan.geometry import solve_layout
    except ImportError as e2:
        _note("solver", e2)
        solve_layout = None

try:
    from validate_all import validate_all, errors_only
except ImportError as e:
    _note("checker", e)
    try:
        from checker import validate_all
        errors_only = None
    except ImportError as e2:
        _note("checker", e2)
        validate_all, errors_only = None, None

if validate_all is None:
    # Last resort: P4's floorplan/validator.py. Its built-in SIZE_TABLE is example values,
    # so P3's real table is passed in (the same thing engine.py does).
    try:
        try:
            from floorplan.validator import validate as _p4_validate
            from floorplan.config import get_checker_size_table
        except ModuleNotFoundError:
            from validator import validate as _p4_validate
            from config import get_checker_size_table

        def validate_all(inp, layout):
            return _p4_validate(inp, layout, size_table=get_checker_size_table(inp["rooms"]))

        errors_only = None
    except ImportError as e3:
        _note("checker", e3)

# Only keep errors for components that ended up missing.
for _name, _loaded in (("engine", solve_request), ("solver", solve_layout), ("checker", validate_all)):
    if _loaded is not None:
        IMPORT_ERRORS.pop(_name, None)

app = FastAPI(
    title="2D Floor Plan Engine (P3)",
    description="Glue REST API bridging Streamlit UI to layout engine and validation",
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
def health():
    return {
        "status": "healthy",
        "service": "floorplan-p3",
        "engine_loaded": solve_request is not None,
        "solver_loaded": solve_layout is not None or solve_request is not None,
        "checker_loaded": validate_all is not None or solve_request is not None,
        "import_errors": IMPORT_ERRORS,
    }


def dispatch_generation(payload: FloorPlanInput):
    """Executes layout generation via engine.py if present, else via runner.py.

    Both paths get the feasibility pre-check and the hard timeout, and never raise.
    """
    if solve_request is not None:
        return execute_engine_request(payload, solve_request)

    return execute_pipeline(
        payload,
        solver_func=solve_layout,
        checker_func=validate_all,
        errors_only_func=errors_only,
    )


def _respond(result):
    if isinstance(result, ErrorResponse):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.model_dump(mode="json"),
        )
    return result


@app.post(
    "/generate",
    response_model=FloorPlanOutput,
    responses={400: {"model": ErrorResponse}},
    tags=["Layout Generation"],
)
def generate(payload: FloorPlanInput):
    return _respond(dispatch_generation(payload))


@app.post(
    "/edit",
    response_model=FloorPlanOutput,
    responses={400: {"model": ErrorResponse}},
    tags=["Layout Generation"],
)
def edit(payload: FloorPlanInput):
    """Legacy edit: re-solve the same input with its pins. Kept so P5's current calls keep working."""
    return _respond(dispatch_generation(payload))


@app.post(
    "/edit-layout",
    response_model=FloorPlanOutput,
    responses={400: {"model": ErrorResponse}},
    tags=["Layout Generation"],
)
def edit_layout_endpoint(payload: EditLayoutRequest):
    """Resize rooms in an existing layout via engine.edit_layout, moving other rooms as little as possible.

    Body: {"input": <FloorPlanInput>, "layout": <one returned layout>,
           "edits": {"Bedroom": {"width": 14}}, "lock": ["Living"]}
    Success: one layout plus "input" (the updated input with pins) for the next edit.
    Failure: 400 with error_code INFEASIBLE and details.nearest = sizes that would work.
    """
    if edit_layout is None:
        return _respond(ErrorResponse(
            error_code="NO_ENGINE_AVAILABLE",
            message="Editing needs P2's engine.py, which is not loaded (see /health).",
        ))
    return _respond(execute_engine_edit(payload, edit_layout))
