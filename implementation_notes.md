# Multi-segment hallway integration (working checkpoint)

## Included changes

- `floorplan/geometry.py`
  - Optional hallway candidate slots, up to six for this MVP.
  - Active segments are output as `hallway_1`, `hallway_2`, ... in `hallway_segments`.
  - Each active segment has a 3-4 ft short side.
  - Sum of all active segments' long sides is at least 12 ft.
  - Optional intervals are included in 2D non-overlap constraints.
  - A single-commodity flow enforces hallway-only network connectivity using shared walls of at least 3 ft.
  - Living rooms, bedrooms and bathrooms connect to at least one active segment.
  - Kitchen-to-first-living adjacency remains in place.
  - Coverage is maximized; among equal-coverage solutions the objective prefers less hallway area and fewer segments.
  - `require_full_coverage=True` remains available as a strict mode.
  - A legacy `hallway` alias is also returned when exactly one segment is active.
- `floorplan/connections.py`
  - `required_pairs()` uses the generic `"hallway"` target.
  - `add_adjacency(..., enforce=...)` supports optional/reified adjacency.
- `floorplan/connections_check.py`
  - Validates combined corridor length, per-segment width, hallway-only connectivity, and room-to-any-segment adjacency.
  - Partial coverage is an H4 warning; excess occupied area remains an error.
- `floorplan/validator.py`
  - Supports multi-segment output and severity on problem records.
- `validate_all.py`
  - Adapts `hallway_segments` and validates hallway-only connectivity.
- `tests/test_multi_hallway_validation.py`
  - Nine checker/adapter tests covering connected/disconnected segments, the 3 ft threshold, combined length, generic room adjacency, warning severity and a multi-segment layout.

## Important scope notes

- Six is a candidate-slot cap for the MVP, not a required segment count. The solver activates only the number it needs. The area-based upper bound can reduce the number of candidate slots further.
- Residual unused-space accessibility (1 ft grid, connected unused components, 3x3 ft fit rule) is not implemented in this checkpoint. It should be added as a separate checker after the solver/checker contract is confirmed.
- The solver's 10-second limit can return a feasible but not proven-optimal result. The output includes `solver_status` and `coverage_optimality_proven`; a partial result with `FEASIBLE` status does not prove full coverage is impossible.
- `require_full_coverage=True` is strict and returns infeasible if exact coverage cannot be found. The default (`False`) maximizes covered area and reports the achieved coverage percentage.

## Validation performed in this environment

- Python syntax compilation passed for all included `.py` files.
- `tests/test_multi_hallway_validation.py`: 9 passed.
- The OR-Tools solver tests could not be executed in this environment because OR-Tools is not installed and package installation is unavailable here. Run the complete suite in the project virtual environment where `requirements.txt` has been installed.

## Commands in the project virtual environment

```bash
python -m py_compile floorplan/*.py validate_all.py tests/*.py
python -m pytest -q
```

For a multi-segment solver run, call `solve_layout(..., include_hallway=True, layout_input=...)` and inspect `result["hallway_segments"]`. Pass the result to `validate_solver_result(inp, result)`.

# P2 integration (branch feature/p2-integration, built on feature/json-solver-adapter)

## How it fits together

`floorplan/engine.py` is the one call: `solve_request(inp)` and `edit_layout(inp, layout, edits, lock=[...])`.
Input check (P4) -> size table (P3 config) -> P1 model + P2 rules -> variants -> doors -> P4 checker -> P3 output schema.

- `geometry.solve_layout` gained three optional arguments, all off by default so P1's behaviour is unchanged: `model_extension` (P2 adds its rules to the same model and supplies the objective), `relative_gap_limit` and `verbose`. A room spec may set `rotatable=True`.
- `preferences.solve_with_preferences` no longer builds a model of its own.
- `input_adapter.build_preference_arguments` passes zones, pins and preferred sizes, which `build_solver_arguments` leaves out.

## Decisions to confirm

- Engine searches up to 2 hallway segments (`MAX_HALLWAY_SEGMENTS`). At 3 or more, CP-SAT cannot prove t20 impossible in 20 s, and with the scoring objective it may return nothing. One segment is tried first.
- `MIN_REACHABLE_COVERAGE = 0.60`: below this a plot is reported as too large (t07). Placeholder for open decision 7.
- `GAP_WEIGHT = 20` points per unused sq ft, so coverage outweighs the other penalties.
- Sizes come from `config.py`. Dining uses the living room limits and utility/store the "other" limits through its aliases, which differ from the example table in `validator.py`. The engine passes the config table to the checker.

## Known gaps

- t04_long_thin expects valid, but `bedroom must NW` is impossible: the plot is 14 ft wide, the NW cell ends at x = 4, and a bedroom at least 10 ft wide has its center at x >= 5. The engine returns conflict. The test input needs changing (P4).
- `place_doors` is a stopgap (middle of each required wall). F2, F3 and F4 are still not checked. Windows are not placed.
- H5 (aspect ratio) and H8 (outer wall access) are in neither the solver nor the checker (P1, P4).
- `schema.RoomInput` allows living, kitchen, bedroom, bathroom and other, while `input_schema.json` also allows dining, utility and store. The engine reports dining as type "living" in output because of the config alias (P3).
- `render.py`, `api.py`, `app.py` and Docker do not exist yet (P3, P5). `draw_plans.py` is a demo drawing until then.

## Commands

```bash
python -m pytest -q
python draw_plans.py
python -m floorplan.json_runner tests/TestCases/t01_standard.json
```

# Team integration (branch integration, 9 Nov)

Built from `p4-checker` (P1 + P2 + P4) with `p3-checker` merged in.

- P3's `config.py` and `schema.py` replace the older copies. Its `api.py` and `runner.py` are added as is.
- P3's test files and `fakes.py` were uploaded into `floorplan/`. They import `tests.fakes`, so they now live in `tests/`.
- `requirements.txt` adds `fastapi`, `uvicorn` and `httpx` (httpx is only for FastAPI's TestClient).
- Engine: output rooms keep the user's type (`dining` stays `dining`), as P3's contract asks.
- Engine: in `edit_layout`, a pin with `"locked": true` stays in place like a room named in `lock`. Kept locks are written back to `input.pins` so they carry over to the next edit, and editing a locked room unlocks it.
- Checked: 323 tests pass. `/health` loads the engine, solver and checker. `/generate` on all 24 inputs gives the expected status except t04 (see above), and returns 3 layouts with `archetype`, `penalties` and `coverage_percent`. `/edit-layout` keeps a locked room in place and returns `nearest` for an impossible size.
- Still missing: P5 has pushed no code. Windows, F2 to F4, H5 and H8 are unchanged.
