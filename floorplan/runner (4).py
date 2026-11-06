"""
floorplan/runner.py
Core pipeline orchestrator executing area pre-checks, CP-SAT solving, and P4 checking.
Owner: P3 (Input and Glue)
"""

from typing import Union, Dict, Any, List, Optional, Tuple, Callable
import inspect

try:
    from floorplan.schema import (
        FloorPlanInput,
        FloorPlanOutput,
        ErrorResponse,
        Layout,
        PlacedRoom,
        HallwaySegment,
    )
    from floorplan.config import (
        ROOM_SIZE_TABLE,
        CIRCULATION_FACTOR,
        SOLVER_TIME_LIMIT_SECONDS,
        SOLVER_MAX_HALLWAY_SEGMENTS,
        resolve_room_type,
        get_p1_room_specs,
    )
except ModuleNotFoundError:
    from schema import (
        FloorPlanInput,
        FloorPlanOutput,
        ErrorResponse,
        Layout,
        PlacedRoom,
        HallwaySegment,
    )
    from config import (
        ROOM_SIZE_TABLE,
        CIRCULATION_FACTOR,
        SOLVER_TIME_LIMIT_SECONDS,
        SOLVER_MAX_HALLWAY_SEGMENTS,
        resolve_room_type,
        get_p1_room_specs,
    )


def split_checker_problems(checker_results: Any) -> Tuple[List[str], List[str]]:
    """Separates hard checker errors from informational/soft warnings extracting clean messages."""
    errors: List[str] = []
    warnings: List[str] = []
    if not checker_results:
        return errors, warnings

    if isinstance(checker_results, dict):
        problems = checker_results.get("errors", []) + checker_results.get("problems", [])
    elif isinstance(checker_results, list):
        problems = checker_results
    else:
        problems = [checker_results]

    for prob in problems:
        if isinstance(prob, dict):
            severity = prob.get("severity", "error").lower()
            msg = prob.get("message") or prob.get("code") or str(prob)
            if severity == "warning":
                warnings.append(str(msg))
            else:
                errors.append(str(msg))
        else:
            errors.append(str(prob))

    return errors, warnings


def check_feasibility(input_data: FloorPlanInput) -> Optional[ErrorResponse]:
    """Pre-check: Validates if buildable area can fit requested rooms + circulation buffer."""
    plot_w, plot_h = input_data.plot
    buildable_w = plot_w - input_data.setbacks.left - input_data.setbacks.right
    buildable_h = plot_h - input_data.setbacks.front - input_data.setbacks.back
    usable_area = buildable_w * buildable_h

    req_min_area = 0
    for r in input_data.rooms:
        canonical = resolve_room_type(r.type)
        min_w, min_h = ROOM_SIZE_TABLE[canonical]["min"]
        req_min_area += (min_w * min_h)

    req_with_circulation = int(req_min_area * (1.0 + CIRCULATION_FACTOR))

    if req_with_circulation > usable_area:
        return ErrorResponse(
            status="infeasible",
            error_code="INFEASIBLE_AREA",
            message=f"Requested rooms require ~{req_with_circulation} sq ft (with 15% circulation), exceeding usable buildable area of {usable_area} sq ft.",
            details={
                "usable_area": usable_area,
                "required_with_circulation": req_with_circulation,
                "deficit": req_with_circulation - usable_area,
            },
        )
    return None


def execute_pipeline(
    input_data: FloorPlanInput,
    solver_func: Optional[Callable] = None,
    checker_func: Optional[Callable] = None,
    errors_only_func: Optional[Callable] = None,
) -> Union[FloorPlanOutput, ErrorResponse]:
    """Full execution pipeline: Feasibility -> P1 Solver -> P4 Validator -> Output."""

    # 1. Feasibility Pre-Check
    feasibility_err = check_feasibility(input_data)
    if feasibility_err:
        return feasibility_err

    if solver_func is None:
        return ErrorResponse(
            error_code="NO_SOLVER_AVAILABLE",
            message="No solver implementation found in environment.",
        )

    # 2. Prepare payload for P1
    payload = input_data.model_dump(exclude_none=True)
    plot_w, plot_h = input_data.plot
    p1_specs = get_p1_room_specs(payload["rooms"], payload.get("pins", []))
    setbacks_dict = payload["setbacks"]

    solver_kwargs = {
        "plot_width": plot_w,
        "plot_height": plot_h,
        "room_specs": p1_specs,
        "setbacks": setbacks_dict,
        "include_hallway": True,
        "layout_input": payload,
        "time_limit_seconds": SOLVER_TIME_LIMIT_SECONDS,
    }
    sig = inspect.signature(solver_func)
    if "max_hallway_segments" in sig.parameters:
        solver_kwargs["max_hallway_segments"] = SOLVER_MAX_HALLWAY_SEGMENTS

    try:
        raw_result = solver_func(**solver_kwargs)
    except Exception as e:
        return ErrorResponse(
            error_code="SOLVER_EXCEPTION",
            message=f"CP-SAT solver raised an unhandled exception: {str(e)}",
        )

    # 3. Handle Solver Response Structure
    if not isinstance(raw_result, dict):
        return ErrorResponse(
            error_code="INVALID_SOLVER_RESULT",
            message="Solver did not return a valid dictionary payload.",
            details={"raw_type": type(raw_result).__name__},
        )

    status = raw_result.get("status", "unknown")
    if status != "success":
        return ErrorResponse(
            status=status,
            error_code="INFEASIBLE_GEOMETRY" if status == "infeasible" else "SOLVER_FAILED",
            message=raw_result.get("message", "The solver could not generate a valid layout."),
            details={"solver_status": status},
        )

    # 4. Standardize Placed Rooms & Hallways
    try:
        placed_rooms_list: List[PlacedRoom] = []
        original_type_map = {r.name: r.type for r in input_data.rooms}

        raw_rooms = raw_result.get("rooms", [])
        if isinstance(raw_rooms, dict):
            room_items = [{"name": k, **v} for k, v in raw_rooms.items()]
        else:
            room_items = raw_rooms

        for item in room_items:
            r_name = item.get("name")
            if not r_name or r_name not in original_type_map:
                return ErrorResponse(
                    error_code="INVALID_SOLVER_RESULT",
                    message=f"Solver returned unknown room '{r_name}' not in input request.",
                    details={"invalid_room": r_name},
                )

            placed_rooms_list.append(
                PlacedRoom(
                    name=r_name,
                    type=original_type_map[r_name],
                    x=item["x"],
                    y=item["y"],
                    w=item.get("w") or item.get("width"),
                    h=item.get("h") or item.get("height"),
                )
            )

        raw_segments = raw_result.get("hallway_segments", [])
        hallway_list = [
            HallwaySegment(
                id=seg.get("id", f"hallway_{idx+1}"),
                x=seg["x"],
                y=seg["y"],
                w=seg.get("w") or seg.get("width"),
                h=seg.get("h") or seg.get("height"),
            )
            for idx, seg in enumerate(raw_segments)
        ]

        layout_obj = Layout(
            score=raw_result.get("score", 0),
            rooms=placed_rooms_list,
            hallway_segments=hallway_list,
            doors=raw_result.get("doors", []),
            windows=raw_result.get("windows", []),
            messages=[],
        )
    except Exception as e:
        return ErrorResponse(
            error_code="INVALID_SOLVER_RESULT",
            message=f"Failed to assemble layout from solver data: {str(e)}",
            details={"error": str(e)},
        )

    # 5. Independent P4 Validation
    if checker_func:
        layout_dict = {
            "rooms": [r.model_dump() for r in layout_obj.rooms],
            "hallway_segments": [h.model_dump() for h in layout_obj.hallway_segments],
        }

        try:
            raw_issues = checker_func(payload, layout_dict)
            if errors_only_func:
                hard_errors = errors_only_func(raw_issues)
                warnings = [
                    p.get("message", str(p)) if isinstance(p, dict) else str(p)
                    for p in raw_issues
                    if p not in hard_errors
                ]
            else:
                hard_errors, warnings = split_checker_problems(raw_issues)

            if hard_errors:
                return ErrorResponse(
                    error_code="VALIDATION_FAILED",
                    message="P4 layout validation detected constraint violations.",
                    details={"errors": hard_errors},
                )

            for w in warnings:
                layout_obj.messages.append(f"Warning: {w}")

        except Exception as e:
            return ErrorResponse(
                error_code="CHECKER_CRASHED",
                message=f"Checker failed during validation: {str(e)}",
                details={"error": str(e)},
            )

    return FloorPlanOutput(layouts=[layout_obj])