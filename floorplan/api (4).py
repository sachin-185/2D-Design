"""
floorplan/api.py
FastAPI web server connecting P5 UI to engine.py (or runner.py fallback).
Owner: P3 (Input and Glue)
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

try:
    from floorplan.schema import FloorPlanInput, FloorPlanOutput, ErrorResponse
    from floorplan.runner import execute_pipeline
except ModuleNotFoundError:
    from schema import FloorPlanInput, FloorPlanOutput, ErrorResponse
    from runner import execute_pipeline

# Check if P2/P4 engine is available
try:
    from floorplan.engine import solve_request, edit_layout
except ImportError:
    try:
        from engine import solve_request, edit_layout
    except ImportError:
        solve_request, edit_layout = None, None

# Fallback imports if engine is not present
try:
    from geometry import solve_layout
except ImportError:
    try:
        from floorplan.geometry import solve_layout
    except ImportError:
        solve_layout = None

try:
    from validate_all import validate_all, errors_only
except ImportError:
    try:
        from checker import validate_all
        errors_only = None
    except ImportError:
        validate_all, errors_only = None, None

app = FastAPI(
    title="2D Floor Plan Engine (P3)",
    description="Glue REST API bridging Streamlit UI to layout engine and validation",
    version="1.0.0",
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
    }


def dispatch_generation(payload: FloorPlanInput):
    """Executes layout generation via engine.py if present, else via runner.py."""
    if solve_request is not None:
        raw_res = solve_request(payload.model_dump(exclude_none=True))
        if isinstance(raw_res, dict) and raw_res.get("status") in ("error", "infeasible", "invalid", "conflict", "timeout"):
            return ErrorResponse(
                status=raw_res.get("status", "error"),
                error_code=raw_res.get("status", "error").upper(),
                message="; ".join(raw_res.get("messages", [])) or "Failed to generate layout.",
                details=raw_res,
            )
        return FloorPlanOutput.model_validate(raw_res)

    return execute_pipeline(
        payload,
        solver_func=solve_layout,
        checker_func=validate_all,
        errors_only_func=errors_only,
    )


@app.post(
    "/generate",
    response_model=FloorPlanOutput,
    responses={400: {"model": ErrorResponse}},
    tags=["Layout Generation"],
)
def generate(payload: FloorPlanInput):
    result = dispatch_generation(payload)
    if isinstance(result, ErrorResponse):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.model_dump(),
        )
    return result


@app.post(
    "/edit",
    response_model=FloorPlanOutput,
    responses={400: {"model": ErrorResponse}},
    tags=["Layout Generation"],
)
def edit(payload: FloorPlanInput):
    result = dispatch_generation(payload)
    if isinstance(result, ErrorResponse):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.model_dump(),
        )
    return result