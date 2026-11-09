"""
floorplan/runner.py
Core pipeline orchestrator executing area pre-checks, CP-SAT solving, and P4 checking.
Owner: P3 (Input and Glue)

Public API (unchanged for api.py / P5):
    check_feasibility(input) -> Optional[ErrorResponse]
    execute_pipeline(input, solver_func, checker_func, errors_only_func) -> FloorPlanOutput | ErrorResponse
    split_checker_problems(results) -> (errors, warnings)
Added:
    execute_engine_request(input, engine_func) -> FloorPlanOutput | ErrorResponse
    process_p1_result(raw, input) -> Layout | ErrorResponse
    run_with_timeout(func, timeout_s, **kwargs)

Neither execute_* function ever raises: every failure becomes an ErrorResponse.
"""

import inspect
import json
import logging
import threading
from typing import Union, Dict, Any, List, Optional, Tuple, Callable

from pydantic import ValidationError

try:
    from floorplan.schema import (
        FloorPlanInput,
        FloorPlanOutput,
        ErrorResponse,
        Layout,
        PlacedRoom,
        HallwaySegment,
        EditLayoutRequest,
    )
    from floorplan.config import (
        ROOM_SIZE_TABLE,
        CIRCULATION_FACTOR,
        SOLVER_TIME_LIMIT_SECONDS,
        SOLVER_MAX_HALLWAY_SEGMENTS,
        SOLVER_TIMEOUT_GRACE_SECONDS,
        ENGINE_HARD_TIMEOUT_SECONDS,
        SOLVER_SUCCESS_STATUSES,
        CHECKER_HARD_SEVERITIES,
        HALLWAY_WIDTH_MIN,
        HALLWAY_MIN_TOTAL_LENGTH,
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
        EditLayoutRequest,
    )
    from config import (
        ROOM_SIZE_TABLE,
        CIRCULATION_FACTOR,
        SOLVER_TIME_LIMIT_SECONDS,
        SOLVER_MAX_HALLWAY_SEGMENTS,
        SOLVER_TIMEOUT_GRACE_SECONDS,
        ENGINE_HARD_TIMEOUT_SECONDS,
        SOLVER_SUCCESS_STATUSES,
        CHECKER_HARD_SEVERITIES,
        HALLWAY_WIDTH_MIN,
        HALLWAY_MIN_TOTAL_LENGTH,
        resolve_room_type,
        get_p1_room_specs,
    )

log = logging.getLogger(__name__)

Result = Union[FloorPlanOutput, ErrorResponse]

# ErrorResponse.status only accepts these values.
_ERROR_STATUSES = {"error", "infeasible", "unknown", "invalid", "conflict", "timeout"}
_ENGINE_FAILURE_STATUSES = {"error", "infeasible", "invalid", "conflict", "timeout", "unknown"}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _error_status(raw_status: Any) -> str:
    s = str(raw_status or "error").lower()
    return s if s in _ERROR_STATUSES else "error"


def _jsonable(obj: Any) -> Any:
    """Make teammate data safe to put in an HTTP response (sets, objects, numpy -> str)."""
    try:
        return json.loads(json.dumps(obj, default=str))
    except (TypeError, ValueError):
        return str(obj)


def _validation_details(exc: ValidationError) -> List[Dict[str, Any]]:
    return [
        {"loc": [str(p) for p in e.get("loc", ())], "msg": e.get("msg", ""), "type": e.get("type", "")}
        for e in exc.errors()
    ]


def _hard_timeout_seconds() -> float:
    return float(SOLVER_TIME_LIMIT_SECONDS + SOLVER_TIMEOUT_GRACE_SECONDS)


def _timeout_error(timeout_s: float) -> ErrorResponse:
    return ErrorResponse(
        status="timeout",
        error_code="SOLVER_TIMEOUT",
        message=f"Layout generation did not finish within {timeout_s:g} seconds. "
                "Try fewer rooms, fewer pins, or a larger plot.",
        details={"timeout_seconds": timeout_s, "solver_time_limit": SOLVER_TIME_LIMIT_SECONDS},
    )


class SolverTimeout(Exception):
    pass


def run_with_timeout(func: Callable, timeout_s: float, *args: Any, **kwargs: Any) -> Any:
    """Run func in a daemon thread; raise SolverTimeout if it overruns.

    CP-SAT releases the GIL, so the API stays responsive while it works. A thread
    cannot be killed, so a runaway solve keeps its CPU until it ends on its own;
    the request, however, is answered on time.
    """
    box: Dict[str, Any] = {}

    def target() -> None:
        try:
            box["result"] = func(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 - re-raised in caller's thread
            box["error"] = exc

    worker = threading.Thread(target=target, name="floorplan-solver", daemon=True)
    worker.start()
    worker.join(timeout_s)
    if worker.is_alive():
        raise SolverTimeout(timeout_s)
    if "error" in box:
        raise box["error"]
    return box.get("result")


def _ensure_input(input_data: Any) -> Union[FloorPlanInput, ErrorResponse]:
    if isinstance(input_data, FloorPlanInput):
        return input_data
    try:
        return FloorPlanInput.model_validate(input_data)
    except ValidationError as exc:
        return ErrorResponse(
            status="invalid",
            error_code="INVALID_INPUT",
            message="Input failed validation.",
            details={"errors": _validation_details(exc)},
        )


# ---------------------------------------------------------------------------
# P4 checker output handling
# ---------------------------------------------------------------------------
def _issue_message(prob: Any) -> str:
    if isinstance(prob, dict):
        return str(prob.get("message") or prob.get("code") or prob)
    return str(prob)


def _issue_list(checker_results: Any) -> List[Any]:
    """Flatten whatever the checker returned into one list of issues."""
    if not checker_results:
        return []
    if isinstance(checker_results, dict):
        out: List[Any] = []
        for key in ("errors", "problems"):
            out.extend(checker_results.get(key) or [])
        for w in checker_results.get("warnings") or []:
            out.append(w if isinstance(w, dict) and "severity" in w
                       else {"severity": "warning", "message": _issue_message(w)})
        return out
    if isinstance(checker_results, (list, tuple)):
        return list(checker_results)
    return [checker_results]


def split_checker_problems(checker_results: Any) -> Tuple[List[str], List[str]]:
    """Separates hard checker errors from informational/soft warnings extracting clean messages.

    Severity "error"/"critical"/"fatal"/"hard" (or none given) -> error.
    Anything else ("warning", "info", "soft") -> warning.
    """
    errors: List[str] = []
    warnings: List[str] = []
    for prob in _issue_list(checker_results):
        if isinstance(prob, dict):
            severity = str(prob.get("severity", "error")).lower()
            (errors if severity in CHECKER_HARD_SEVERITIES else warnings).append(_issue_message(prob))
        else:
            errors.append(str(prob))
    return errors, warnings


def run_checker(
    checker_func: Callable,
    errors_only_func: Optional[Callable],
    payload: Dict[str, Any],
    layout_obj: Layout,
) -> Optional[ErrorResponse]:
    """Run P4. Returns ErrorResponse on hard errors or crash; otherwise appends warnings to the layout."""
    layout_dict = {
        "rooms": [r.model_dump() for r in layout_obj.rooms],
        "hallway_segments": [h.model_dump() for h in layout_obj.hallway_segments],
    }
    try:
        raw_issues = checker_func(payload, layout_dict)

        if errors_only_func:
            hard = list(errors_only_func(raw_issues) or [])
            hard_errors = [_issue_message(p) for p in hard]
            warnings = [_issue_message(p) for p in _issue_list(raw_issues) if p not in hard]
        else:
            hard_errors, warnings = split_checker_problems(raw_issues)
    except Exception as e:  # noqa: BLE001
        log.exception("P4 checker crashed")
        return ErrorResponse(
            error_code="CHECKER_CRASHED",
            message=f"Checker failed during validation: {e}",
            details={"error": str(e), "layout": layout_obj.model_dump()},
        )

    if hard_errors:
        return ErrorResponse(
            error_code="VALIDATION_FAILED",
            message="P4 layout validation detected constraint violations.",
            details={
                "errors": hard_errors,
                "warnings": warnings,
                # So P5 can still draw the failed plan and highlight the problems.
                "layout": layout_obj.model_dump(),
            },
        )

    for w in warnings:
        layout_obj.messages.append(f"Warning: {w}")
    return None


# ---------------------------------------------------------------------------
# Feasibility
# ---------------------------------------------------------------------------
def _buildable(input_data: FloorPlanInput) -> Tuple[int, int]:
    plot_w, plot_h = input_data.plot
    return (
        plot_w - input_data.setbacks.left - input_data.setbacks.right,
        plot_h - input_data.setbacks.front - input_data.setbacks.back,
    )


def _room_min_dims(room: Any, pin_lookup: Dict[str, Any]) -> Tuple[int, int]:
    min_w, min_h = ROOM_SIZE_TABLE[resolve_room_type(room.type)]["min"]
    pin = pin_lookup.get(room.name)
    if pin is not None:
        min_w = pin.width or min_w
        min_h = pin.height or min_h
    return min_w, min_h


def check_feasibility(input_data: FloorPlanInput) -> Optional[ErrorResponse]:
    """Pre-check: every room fits the buildable area, and total area fits with circulation.

    Circulation = max(15% of room area, one minimum hallway of 3 x 12 ft).
    Pinned sizes are used instead of table minimums.
    """
    buildable_w, buildable_h = _buildable(input_data)
    usable_area = buildable_w * buildable_h
    pin_lookup = {p.room: p for p in input_data.pins}

    req_min_area = 0
    for r in input_data.rooms:
        min_w, min_h = _room_min_dims(r, pin_lookup)
        pinned = r.name in pin_lookup
        fits = (min_w <= buildable_w and min_h <= buildable_h) or (
            not pinned and min_h <= buildable_w and min_w <= buildable_h
        )
        if not fits:
            return ErrorResponse(
                status="infeasible",
                error_code="ROOM_DOES_NOT_FIT",
                message=f"Room '{r.name}' needs at least {min_w} x {min_h} ft, but the buildable "
                        f"area is only {buildable_w} x {buildable_h} ft.",
                details={"room": r.name, "required": [min_w, min_h],
                         "buildable": [buildable_w, buildable_h]},
            )
        req_min_area += min_w * min_h

    circulation = max(int(req_min_area * CIRCULATION_FACTOR), HALLWAY_WIDTH_MIN * HALLWAY_MIN_TOTAL_LENGTH)
    req_with_circulation = req_min_area + circulation

    if req_with_circulation > usable_area:
        return ErrorResponse(
            status="infeasible",
            error_code="INFEASIBLE_AREA",
            message=f"Requested rooms require ~{req_with_circulation} sq ft (rooms {req_min_area} + "
                    f"circulation {circulation}), exceeding usable buildable area of {usable_area} sq ft.",
            details={
                "usable_area": usable_area,
                "required_with_circulation": req_with_circulation,
                "deficit": req_with_circulation - usable_area,
            },
        )
    return None


# ---------------------------------------------------------------------------
# P1 boundary
# ---------------------------------------------------------------------------
def build_solver_kwargs(input_data: FloorPlanInput, solver_func: Callable) -> Dict[str, Any]:
    """Keyword arguments for geometry.solve_layout, filtered to what it accepts."""
    payload = input_data.model_dump(exclude_none=True)
    plot_w, plot_h = input_data.plot
    kwargs: Dict[str, Any] = {
        "plot_width": plot_w,
        "plot_height": plot_h,
        "room_specs": get_p1_room_specs(payload["rooms"], payload.get("pins", [])),
        "setbacks": payload["setbacks"],
        "include_hallway": True,
        "layout_input": payload,
        "time_limit_seconds": SOLVER_TIME_LIMIT_SECONDS,
        "max_hallway_segments": SOLVER_MAX_HALLWAY_SEGMENTS,
        # geometry.solve_layout prints CP-SAT stats on every solve unless told not to.
        "verbose": False,
    }
    try:
        params = inspect.signature(solver_func).parameters
    except (TypeError, ValueError):
        return kwargs  # builtin / C function: pass everything
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return kwargs
    return {k: v for k, v in kwargs.items() if k in params}


def process_p1_result(raw_result: Any, input_data: FloorPlanInput) -> Union[Layout, ErrorResponse]:
    """Validate P1's dict and build a Layout (room types restored from the input)."""
    if not isinstance(raw_result, dict):
        return ErrorResponse(
            error_code="INVALID_SOLVER_RESULT",
            message="Solver did not return a valid dictionary payload.",
            details={"raw_type": type(raw_result).__name__},
        )

    status = str(raw_result.get("status", "unknown")).lower()
    if status not in SOLVER_SUCCESS_STATUSES:
        return ErrorResponse(
            status="timeout" if status == "unknown" else _error_status(status),
            error_code="INFEASIBLE_GEOMETRY" if status == "infeasible"
            # geometry.solve_layout reports its time limit as "unknown"
            else "SOLVER_TIMEOUT" if status in ("timeout", "unknown") else "SOLVER_FAILED",
            message=raw_result.get("message", "The solver could not generate a valid layout."),
            details={"solver_status": status},
        )

    original_type_map = {r.name: r.type for r in input_data.rooms}
    raw_rooms = raw_result.get("rooms", [])
    room_items = ([{"name": k, **v} for k, v in raw_rooms.items()]
                  if isinstance(raw_rooms, dict) else list(raw_rooms or []))

    try:
        placed_rooms: List[PlacedRoom] = []
        seen: set = set()
        for item in room_items:
            r_name = item.get("name")
            if not r_name or r_name not in original_type_map:
                return ErrorResponse(
                    error_code="INVALID_SOLVER_RESULT",
                    message=f"Solver returned unknown room '{r_name}' not in input request.",
                    details={"invalid_room": r_name},
                )
            if r_name in seen:
                return ErrorResponse(
                    error_code="INVALID_SOLVER_RESULT",
                    message=f"Solver placed room '{r_name}' more than once.",
                    details={"duplicate_room": r_name},
                )
            seen.add(r_name)
            placed_rooms.append(PlacedRoom(
                name=r_name,
                type=original_type_map[r_name],
                x=item["x"],
                y=item["y"],
                w=item.get("w") or item.get("width"),
                h=item.get("h") or item.get("height"),
            ))

        missing = [n for n in original_type_map if n not in seen]
        if missing:
            return ErrorResponse(
                error_code="INVALID_SOLVER_RESULT",
                message=f"Solver did not place: {', '.join(missing)}.",
                details={"missing_rooms": missing},
            )

        hallway_list = [
            HallwaySegment(
                id=seg.get("id") or f"hallway_{idx + 1}",
                x=seg["x"],
                y=seg["y"],
                w=seg.get("w") or seg.get("width"),
                h=seg.get("h") or seg.get("height"),
            )
            for idx, seg in enumerate(raw_result.get("hallway_segments") or [])
        ]

        solver_messages = raw_result.get("messages") or []
        return Layout(
            score=raw_result.get("score") or 0,
            rooms=placed_rooms,
            hallway_segments=hallway_list,
            doors=raw_result.get("doors") or [],
            windows=raw_result.get("windows") or [],
            messages=[str(m) for m in solver_messages] if isinstance(solver_messages, list) else [],
        )
    except (KeyError, TypeError, ValueError, ValidationError) as e:
        return ErrorResponse(
            error_code="INVALID_SOLVER_RESULT",
            message=f"Failed to assemble layout from solver data: {e}",
            details={"error": str(e)},
        )


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------
def execute_pipeline(
    input_data: FloorPlanInput,
    solver_func: Optional[Callable] = None,
    checker_func: Optional[Callable] = None,
    errors_only_func: Optional[Callable] = None,
    hard_timeout_seconds: Optional[float] = None,
) -> Result:
    """Full execution pipeline: Feasibility -> P1 Solver (time-boxed) -> P4 Validator -> Output."""
    try:
        validated = _ensure_input(input_data)
        if isinstance(validated, ErrorResponse):
            return validated
        input_data = validated

        # 1. Feasibility pre-check
        feasibility_err = check_feasibility(input_data)
        if feasibility_err:
            return feasibility_err

        if solver_func is None:
            return ErrorResponse(
                error_code="NO_SOLVER_AVAILABLE",
                message="No solver implementation found in environment.",
            )

        # 2. P1 solve, with a hard time box
        timeout_s = hard_timeout_seconds or _hard_timeout_seconds()
        try:
            raw_result = run_with_timeout(solver_func, timeout_s, **build_solver_kwargs(input_data, solver_func))
        except SolverTimeout:
            return _timeout_error(timeout_s)
        except Exception as e:  # noqa: BLE001
            log.exception("P1 solver raised")
            return ErrorResponse(
                error_code="SOLVER_EXCEPTION",
                message=f"CP-SAT solver raised an unhandled exception: {e}",
            )

        # 3. Standardize placed rooms & hallways
        layout_obj = process_p1_result(raw_result, input_data)
        if isinstance(layout_obj, ErrorResponse):
            return layout_obj

        # 4. Independent P4 validation
        if checker_func:
            check_err = run_checker(checker_func, errors_only_func,
                                    input_data.model_dump(exclude_none=True), layout_obj)
            if check_err:
                return check_err

        return FloorPlanOutput(layouts=[layout_obj])

    except Exception as e:  # noqa: BLE001 - API must never return a bare 500
        log.exception("Unexpected pipeline failure")
        return ErrorResponse(error_code="INTERNAL_ERROR", message=f"{type(e).__name__}: {e}")


def _engine_result(raw_res: Any) -> Result:
    """Turn engine.solve_request / edit_layout output into FloorPlanOutput or ErrorResponse.

    Engine statuses: valid -> success; infeasible / conflict / invalid / timeout -> error.
    Failure extras (conflict_rooms, nearest, messages) stay in ErrorResponse.details.
    """
    if not isinstance(raw_res, dict):
        return ErrorResponse(
            error_code="INVALID_ENGINE_RESULT",
            message="Engine did not return a dictionary.",
            details={"raw_type": type(raw_res).__name__},
        )

    status = str(raw_res.get("status", "")).lower()
    messages = raw_res.get("messages") or []
    if not isinstance(messages, list):
        messages = [messages]

    if status in _ENGINE_FAILURE_STATUSES or not raw_res.get("layouts"):
        return ErrorResponse(
            status=_error_status(status),
            error_code=(status or "error").upper(),
            message="; ".join(_issue_message(m) for m in messages) or "Failed to generate layout.",
            details=_jsonable(raw_res),
        )

    try:
        return FloorPlanOutput.model_validate({
            "layouts": raw_res["layouts"],
            "messages": [_issue_message(m) for m in messages],
            "input": raw_res.get("input"),
        })
    except ValidationError as exc:
        return ErrorResponse(
            error_code="INVALID_ENGINE_RESULT",
            message="Engine output does not match FloorPlanOutput.",
            details={"errors": _validation_details(exc)},
        )


def _run_engine(func: Callable, timeout_s: Optional[float], *args: Any, **kwargs: Any) -> Result:
    timeout_s = timeout_s or float(ENGINE_HARD_TIMEOUT_SECONDS)
    try:
        raw_res = run_with_timeout(func, timeout_s, *args, **kwargs)
    except SolverTimeout:
        return _timeout_error(timeout_s)
    except Exception as e:  # noqa: BLE001
        log.exception("Engine raised")
        return ErrorResponse(error_code="ENGINE_EXCEPTION", message=f"Layout engine raised: {e}")
    return _engine_result(raw_res)


def execute_engine_request(
    input_data: FloorPlanInput,
    engine_func: Callable,
    hard_timeout_seconds: Optional[float] = None,
) -> Result:
    """Run engine.solve_request(inp). Never raises.

    No P3 feasibility pre-check here: the engine runs its own (check_area) and, by team
    decision, may return a no-hallway layout for small plots that P3's hallway minimum
    would wrongly reject.
    """
    try:
        validated = _ensure_input(input_data)
        if isinstance(validated, ErrorResponse):
            return validated
        return _run_engine(engine_func, hard_timeout_seconds, validated.model_dump(exclude_none=True))
    except Exception as e:  # noqa: BLE001
        log.exception("Unexpected engine pipeline failure")
        return ErrorResponse(error_code="INTERNAL_ERROR", message=f"{type(e).__name__}: {e}")


def execute_engine_edit(
    request: Union[EditLayoutRequest, Dict[str, Any]],
    edit_func: Callable,
    hard_timeout_seconds: Optional[float] = None,
) -> Result:
    """Run engine.edit_layout(inp, layout, edits, lock). Never raises.

    On success the output carries the updated "input" (edits turned into pins).
    On failure, details hold the engine's "nearest" sizes that would work.
    """
    try:
        if not isinstance(request, EditLayoutRequest):
            try:
                request = EditLayoutRequest.model_validate(request)
            except ValidationError as exc:
                return ErrorResponse(status="invalid", error_code="INVALID_INPUT",
                                     message="Edit request failed validation.",
                                     details={"errors": _validation_details(exc)})
        layout = request.layout.model_dump()
        return _run_engine(
            edit_func, hard_timeout_seconds,
            request.input.model_dump(exclude_none=True),
            {"rooms": layout["rooms"], "hallway_segments": layout["hallway_segments"]},
            {room: dict(sides) for room, sides in request.edits.items()},
            lock=list(request.lock) or None,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("Unexpected engine edit failure")
        return ErrorResponse(error_code="INTERNAL_ERROR", message=f"{type(e).__name__}: {e}")
