"""Warnings (for example unused area) must not make a layout invalid; errors must."""
from floorplan.validator import violation
from validate_all import errors_only, is_valid, validate_all, warnings_only

INPUT = {
    "plot": [30, 20],
    "setbacks": {"left": 0, "right": 0, "front": 0, "back": 0},
    "entrance": "S",
    "north": "up",
    "rooms": [
        {"name": "living", "type": "living"},
        {"name": "bedroom_1", "type": "bedroom"},
    ],
}

# Hallway 12 x 3 along the top of living; bedroom touches the hallway end. 15 sq ft unused at the right.
LAYOUT = {
    "rooms": [
        {"name": "living", "x": 0, "y": 0, "w": 12, "h": 12},
        {"name": "bedroom_1", "x": 12, "y": 3, "w": 12, "h": 12},
    ],
    "hallway_segments": [{"id": "hallway_1", "x": 0, "y": 12, "w": 12, "h": 3}],
}


def test_problem_without_severity_counts_as_error():
    old_style = {"code": "H1", "message": "x", "rooms": []}
    assert errors_only([old_style]) == [old_style]
    assert warnings_only([old_style]) == []


def test_default_severity_from_violation_is_error():
    assert violation("H3", "overlap", ["a", "b"])["severity"] == "error"


def test_warning_alone_keeps_a_layout_valid():
    problems = [violation("H4", "unused area", [], "warning")]
    assert is_valid(problems)
    assert errors_only(problems) == []
    assert len(warnings_only(problems)) == 1


def test_one_error_among_warnings_makes_a_layout_invalid():
    problems = [violation("H4", "unused area", [], "warning"), violation("H3", "overlap", ["a", "b"])]
    assert not is_valid(problems)
    assert [p["code"] for p in errors_only(problems)] == ["H3"]
    assert [p["code"] for p in warnings_only(problems)] == ["H4"]


def test_empty_list_is_valid():
    assert is_valid([])


def test_partial_coverage_layout_reports_a_warning_but_no_error():
    problems = validate_all(INPUT, LAYOUT)
    assert any(p["code"] == "H4" and p["severity"] == "warning" for p in problems)
    # The only error left (if any) must not be about coverage.
    assert all(p["code"] != "H4" for p in errors_only(problems))