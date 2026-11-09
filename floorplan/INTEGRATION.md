# Floor Plan Engine: Integration Contracts (P3, v1.3)

Source of truth: `floorplan/config.py`, `schema.py`, `runner.py`, `api.py`. Everything P3 hands to
teammates is a plain Python dict (`model_dump(exclude_none=True)`); nobody else needs Pydantic.

## Folder layout (required by engine.py's imports)

```
project\
├── validate_all.py          P4  (engine imports it as a top-level module)
└── floorplan\
    ├── config.py schema.py runner.py api.py      P3
    ├── geometry.py                               P1
    ├── engine.py preferences.py input_adapter.py P2
    ├── connections.py                            (whoever owns it)
    └── validator.py                              P4
```
Run everything from `project\`. Python 3.12 (ortools has no build for 3.14/3.15 yet).

## Room types

Canonical: `living`, `kitchen`, `bedroom`, `bathroom`.
Aliases: `dining`, `study` → living; `utility`, `store`, `storage`, `laundry` → kitchen.
Placed rooms keep the user's original type (e.g. `dining`) in the output.
At least one room must be explicitly `living` (P1's entrance anchor). Max 10 rooms.
Room names are trimmed and must be unique; `hallway` / `hallway_<n>` are reserved.
Only bathrooms may use `attached_to`, and it must name a bedroom.

## P1: `geometry.solve_layout(**kwargs) -> dict`

P3 calls it with keyword arguments, **filtered to the parameters the function declares**
(all are passed if it accepts `**kwargs`):

| kwarg | value |
|---|---|
| `plot_width`, `plot_height` | whole feet |
| `room_specs` | `{name: {min_width, max_width, min_height, max_height}}` (pins fix a dimension) |
| `setbacks` | `{front, back, left, right}` |
| `include_hallway` | `True` |
| `layout_input` | full input dict (zones, entrance, north, pins…) |
| `time_limit_seconds` | `10`: please set CP-SAT `max_time_in_seconds` to this |
| `max_hallway_segments` | `2` |

**Return**
```json
{"status": "success", "score": 87.5,
 "rooms": {"Living": {"x": 0, "y": 3, "w": 12, "h": 12}},
 "hallway_segments": [{"id": "hallway_1", "x": 0, "y": 0, "w": 34, "h": 3}],
 "doors": [], "windows": [], "messages": []}
```
- `status`: `success` (also accepted: `ok`, `optimal`, `feasible`). `infeasible` and `timeout` are reported as such; anything else becomes `SOLVER_FAILED`.
- `rooms` may be a dict keyed by name or a list with `name`. `width`/`height` accepted for `w`/`h`.
- **Every input room must be placed exactly once.** Missing or duplicate rooms are rejected.
- `score` may be an int or float.
- **Hard timeout:** P3 stops waiting after 10 s + 2 s grace and returns `SOLVER_TIMEOUT`.

## P4: `validate_all(payload, layout) -> issues` and optional `errors_only(issues)`

- `layout` = `{"rooms": [{name, type, x, y, w, h}], "hallway_segments": [{id, x, y, w, h}]}`
- Issues can be a list, or a dict with `errors` / `problems` / `warnings` lists.
- Without `errors_only`: severity `error`, `critical`, `fatal`, `hard` (or none given) = hard error. Anything else (`warning`, `info`) = warning.
- With `errors_only`: whatever it returns are hard errors; the rest are warnings.
- Hard errors → `VALIDATION_FAILED`; warnings are added to `layout.messages` as `"Warning: …"`.

## Engine (P2): `engine.solve_request(inp)` and `engine.edit_layout(inp, layout, edits, lock)`

When `engine.py` loads, `/generate` uses `solve_request` instead of the P1+P4 path.
- P3 passes the validated input as a dict. P3's area pre-check is **skipped** on this path: the engine runs its own `check_area`, and may return a no-hallway plan for small plots (team decision item 8).
- Engine statuses: `valid` → success (layouts + run-level `messages`). `infeasible`, `conflict` (with `conflict_rooms`), `invalid`, `timeout` → HTTP 400; everything the engine returned is in `details`.
- Per-layout extras (`archetype`, `penalties`, `coverage_percent`) are kept in the response.
- Backstop: P3 stops waiting after `ENGINE_HARD_TIMEOUT_SECONDS` (60 s). The engine makes several solver calls per request, so the per-solve 10 s limit can't be the total. **Open decision:** what is the agreed end-to-end limit?
- Engine room `type` in output is canonical (`dining` → `living`); the P1+P4 path keeps the original. **Open decision:** pick one.

`edit_layout` powers `POST /edit-layout` (see below).

## P5: REST API (`uvicorn floorplan.api:app --port 8000`)

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/health` | none | loaded flags + `import_errors` (why a module failed to load) |
| POST | `/generate` | `FloorPlanInput` | `{"layouts": [Layout]}` |
| POST | `/edit` | `FloorPlanInput` (edits = pins) | `{"layouts": [Layout]}` (legacy, unchanged) |
| POST | `/edit-layout` | `{input, layout, edits, lock}` | one layout + updated `input` (needs engine) |

Every success body: `{"layouts": [...], "messages": [...], "input": null | {...}}`.

**`/edit-layout` body**
```json
{"input": {...the FloorPlanInput...},
 "layout": {...one layout from the last response...},
 "edits": {"Bedroom": {"width": 14}},
 "lock": ["Living"]}
```
On success, send the returned `input` as the next edit's `input` so pins accumulate.
If the size can't be built: 400, `error_code: "INFEASIBLE"`, `details.nearest` = e.g. `{"Bedroom": {"width": 13}}`.

**Errors:** HTTP 400, body `{"detail": {"status", "error_code", "message", "details"}}`. Invalid request bodies are FastAPI's standard 422.

| error_code | When |
|---|---|
| `ROOM_DOES_NOT_FIT` | A room's minimum (or pinned) size is bigger than the buildable area |
| `INFEASIBLE_AREA` | Rooms + circulation (max of 15% or one 3×12 hallway) exceed buildable area |
| `NO_SOLVER_AVAILABLE` | P1 not importable (see `/health`) |
| `SOLVER_TIMEOUT` | Over 12 s |
| `SOLVER_EXCEPTION` / `SOLVER_FAILED` / `INFEASIBLE_GEOMETRY` | P1 crashed / failed / found no layout |
| `INVALID_SOLVER_RESULT` | P1 output malformed, unknown, missing or duplicate rooms |
| `VALIDATION_FAILED` | P4 hard errors; `details.layout` holds the plan so P5 can still draw it |
| `CHECKER_CRASHED` | P4 raised; `details.layout` included |
| `ENGINE_EXCEPTION` / `INVALID_ENGINE_RESULT` | Engine crashed / returned a bad shape |
| `INFEASIBLE` / `CONFLICT` / `INVALID` / `TIMEOUT` | Engine status, with its details |
| `NO_ENGINE_AVAILABLE` | `/edit-layout` called without engine.py |
| `INTERNAL_ERROR` | Anything unexpected (never a bare 500) |

## Open issues found in teammates' files (v1.3 review)

- **P2 `engine.py`**: the copy shared is missing the opening `"""` on line 1, which is a SyntaxError and the engine never loads. Check the real file.
- **P4 `validate_all.py`**: required by engine.py (`adapt_solver_result, errors_only, validate_all, warnings_only`) and not shared yet. Must sit in the project root.
- **P4 `validator.py`**: `check_input` is defined twice (the second wins; delete the first). Its `SIZE_TABLE` gives `dining` 10×10–16×16 and `utility`/`store` 4×4–8×8, but P3's `config.py` maps dining → living (12×12–20×20) and utility/store → kitchen (8×8–12×12). **Team decision needed** on the real sizes; P3 will add dedicated entries if agreed.
- **P2 engine runtime**: `solve_with_preferences` may call P1 twice (1 slot, then 2), and `generate_variants` tries up to 6 shapes, each with a 10 s limit. A request can exceed P3's 60 s backstop. Suggest the engine pass a shared deadline.

## Changes in v1.3 (P3)

- P1 is called with `verbose=False` (it printed CP-SAT stats on every solve).
- P1's `"unknown"` status (its time-limit result) now maps to `SOLVER_TIMEOUT`, not `SOLVER_FAILED`.
- If `validate_all.py` is missing, the API falls back to P4's `floorplan/validator.validate`, passing P3's real size table (`config.get_checker_size_table`).
- New `tests/test_real_integration.py`: runs against teammates' real modules when present, skips otherwise.

## Changes in v1.2 (P3)

- Float layout scores accepted (the engine's own `FloorPlanOutput(...)` call crashed on e.g. 88.4).
- Engine `valid` status handled; engine run messages and per-layout extras kept.
- New `POST /edit-layout` wired to `engine.edit_layout`; `/edit` unchanged.
- Engine path: own 60 s backstop; P3 area pre-check skipped (engine checks area itself).
- Interface test now freezes the engine's full config import and `ROOM_SIZE_TABLE` shape.

## Changes in v1.1 (P3)

- Hard timeout on P1 and engine (previously none: a hung solver blocked the API forever).
- Unexpected solver statuses no longer crash the API.
- `info` checker issues are warnings, not errors.
- A dict from `validate_all` with `errors_only` no longer crashes.
- Solver output that omits or duplicates a room is rejected.
- Float scores accepted (`Layout.score` is now float).
- Room names / `attached_to` / pin rooms are trimmed; duplicate pins rejected.
- Feasibility: per-room fit check; pinned sizes used; circulation is at least one 3×12 hallway.
- Engine path now gets the pre-check and timeout too.
- `/health` reports why modules failed to import.
- Error `details.errors` is always a list of message strings; failed layouts included for P5.
