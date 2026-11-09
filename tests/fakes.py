"""
Stand-ins for P1 (geometry.solve_layout), P4 (validate_all / errors_only) and
engine.solve_request, matching their call signatures. Test use only.
"""
import time


def fake_solve_layout(plot_width=20, plot_height=12, room_specs=None, setbacks=None,
                      include_hallway=False, layout_input=None, require_full_coverage=False,
                      max_hallway_segments=6, time_limit_seconds=10, model_extension=None,
                      relative_gap_limit=0.10, verbose=True):
    """Same signature as P1's geometry.solve_layout."""
    """Shelf packer: hallway along the bottom, rooms in rows above, coords relative to buildable."""
    assert isinstance(room_specs, dict) and isinstance(layout_input, dict)
    bw = plot_width - setbacks.get("left", 0) - setbacks.get("right", 0)
    bh = plot_height - setbacks.get("front", 0) - setbacks.get("back", 0)
    x, y, shelf = 0, 3, 0
    rooms = {}
    for name, spec in room_specs.items():
        w, h = spec["min_width"], spec["min_height"]
        if x + w > bw:
            x, y, shelf = 0, y + shelf, 0
        if x + w > bw or y + h > bh:
            return {"status": "infeasible", "message": "fake packer ran out of space"}
        rooms[name] = {"x": x, "y": y, "w": w, "h": h}
        x, shelf = x + w, max(shelf, h)
    return {
        "status": "success",
        "score": 87.5,
        "rooms": rooms,
        "hallway_segments": [{"id": "hallway_1", "x": 0, "y": 0, "w": bw, "h": 3}],
    }


def solver_without_layout_input(plot_width, plot_height, room_specs, setbacks,
                                include_hallway, time_limit_seconds):
    """An older P1 signature: no layout_input / max_hallway_segments."""
    return fake_solve_layout(plot_width, plot_height, room_specs, setbacks, include_hallway,
                             {}, time_limit_seconds)


def slow_solver(**kwargs):
    time.sleep(3)
    return {"status": "success", "rooms": {}}


def crashing_solver(**kwargs):
    raise RuntimeError("CP-SAT exploded")


def validate_all(payload, layout):
    assert isinstance(payload, dict) and isinstance(layout, dict)
    return [
        {"severity": "warning", "code": "W1", "message": "Kitchen far from dining"},
        {"severity": "info", "code": "I1", "message": "Score computed"},
    ]


def validate_all_failing(payload, layout):
    return [
        {"severity": "error", "code": "E1", "message": "Rooms overlap"},
        {"severity": "warning", "code": "W1", "message": "Small window"},
    ]


def errors_only(issues):
    return [i for i in issues if i.get("severity") == "error"]


def checker_returning_dict(payload, layout):
    return {"errors": [], "warnings": ["Bathroom has no window"]}


def _engine_layout(payload):
    bw = payload["plot"][0] - payload["setbacks"].get("left", 0) - payload["setbacks"].get("right", 0)
    res = fake_solve_layout(
        payload["plot"][0], payload["plot"][1],
        {r["name"]: {"min_width": 12, "min_height": 12} for r in payload["rooms"]},
        payload["setbacks"], True, payload, 10,
    )
    return {
        "score": 91.25,
        "rooms": [{"name": n, "type": "living", "x": v["x"], "y": v["y"], "w": v["w"], "h": v["h"]}
                  for n, v in res["rooms"].items()],
        "hallway_segments": res["hallway_segments"],
        "doors": [{"between": ["outside", "Living"], "x": 6, "y": 0}],
        "windows": [],
        "messages": [],
        # extras the real engine merges in after schema validation
        "archetype": "linear", "penalties": {"zone": 0}, "coverage_percent": 64.3,
    }


def engine_ok(payload, count=3, time_limit_seconds=10, max_hallway_segments=2,
              locked_rooms=None, previous_layout=None):
    """Same signature and result shape as engine.solve_request."""
    return {"status": "valid", "layouts": [_engine_layout(payload)],
            "messages": ["Dropped a layout the checker rejected: [H3] hallway too narrow"]}


def engine_edit_ok(inp, layout, edits, lock=None, time_limit_seconds=10, max_hallway_segments=2):
    """Same signature and result shape as engine.edit_layout."""
    assert isinstance(inp, dict) and isinstance(layout, dict) and isinstance(edits, dict)
    pins = {p["room"]: dict(p) for p in inp.get("pins", [])}
    for room, values in edits.items():
        pins.setdefault(room, {"room": room}).update(values)
    new_inp = {**inp, "pins": list(pins.values())}
    return {"status": "valid", "layouts": [_engine_layout(inp)], "messages": [], "input": new_inp}


def engine_edit_infeasible(inp, layout, edits, lock=None, **kw):
    return {"status": "infeasible", "layouts": [], "nearest": {"Bedroom": {"width": 13}},
            "messages": ["This edit cannot be built: Bedroom width 16 ft. Nearest Bedroom width that works: 13 ft."]}
