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
