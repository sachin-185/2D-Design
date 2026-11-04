"""Check one saved layout against its input from the command line (P4).

    python validate_file.py input.json layout.json
    python validate_file.py input.json layout.json --json
    python validate_file.py input.json p3_output.json --layout-index 1

Input file: a plain input, or a test case file {"name", "input", "expect"} (the "input" part is used).
Layout file, any of:
  - the checker format: {"rooms": [ ... ], "hallway_segments": [ ... ]}
  - P1's raw solver result: {"status": "success", "rooms": {name: {...}}, ...}
  - P3's output: {"layouts": [layout, ...]} (pick one with --layout-index, default 0)

Exit codes: 0 valid (warnings allowed), 1 the layout has errors, 2 a file could not be read or understood.
The same checks are available from Python with check_files(input_path, layout_path).
"""
import argparse
import json
import sys
from unicodedata import name

from validate_all import adapt_solver_result, errors_only, validate_all, warnings_only

EXIT_VALID = 0
EXIT_INVALID = 1
EXIT_FILE_PROBLEM = 2

RECT_FIELDS = ("x", "y", "w", "h")
SOLVER_SUCCESS = "success"


class FileProblem(Exception):
    """A file is missing, is not JSON, or does not have the shape the checker needs."""


# ---------------------------------------------------------------------------
# Reading files
# ---------------------------------------------------------------------------

def read_json(path):
    """Return the parsed JSON in path. utf-8-sig also accepts files saved with a BOM by Windows tools."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileProblem(f"file not found: {path}") from None
    except json.JSONDecodeError as e:
        raise FileProblem(f"{path} is not valid JSON (line {e.lineno}, column {e.colno}: {e.msg})") from None
    except (OSError, UnicodeDecodeError) as e:
        raise FileProblem(f"could not read {path}: {e}") from None


def load_input(path):
    """The input dict from a plain input file or from a test case file."""
    data = read_json(path)
    if isinstance(data, dict) and isinstance(data.get("input"), dict):
        data = data["input"]
    check_input_shape(data, path)
    return data


def load_layout(path, layout_index=0):
    """The layout in the checker format, whichever supported format the file uses."""
    return to_layout(read_json(path), path, layout_index)


def to_layout(data, path="layout", layout_index=0):
    """Convert any supported layout format to the checker format and check its shape."""
    if not isinstance(data, dict):
        raise FileProblem(f"{path}: the layout must be a JSON object")

    if "layouts" in data:  # P3's output: a list of alternative layouts
        layouts = data["layouts"]
        if not isinstance(layouts, list) or not layouts:
            raise FileProblem(f"{path}: 'layouts' must be a non-empty list")
        if not 0 <= layout_index < len(layouts):
            raise FileProblem(
                f"{path}: layout index {layout_index} does not exist (the file has {len(layouts)} layouts)")
        return to_layout(layouts[layout_index], f"{path} layouts[{layout_index}]")

    if "status" in data or isinstance(data.get("rooms"), dict):  # P1's raw solver result
        if data.get("status") != SOLVER_SUCCESS:
            reason = data.get("message") or "no message"
            raise FileProblem(f"{path}: the solver result has status {data.get('status')!r} ({reason})")
        if not isinstance(data.get("rooms"), dict):
            raise FileProblem(f"{path}: a solver result must have a 'rooms' dictionary")
        for name, room in data["rooms"].items():
            if not isinstance(room, dict):
                raise FileProblem(f"{sys.path}: room '{name}' must be a dictionary")    
        try:
            layout = adapt_solver_result(data)
        except ValueError as e:
            raise FileProblem(f"{sys.path}: {e}") from e

    else:
        layout = data

    check_layout_shape(layout, path)
    return layout


# ---------------------------------------------------------------------------
# Shape checks: stop things that would crash the checker, report them clearly.
# Rule problems (overlap, sizes, ...) are left to validate_all.
# ---------------------------------------------------------------------------

def is_whole_number(value):
    """True for an int (bool is excluded, although Python treats it as an int)."""
    return isinstance(value, int) and not isinstance(value, bool)


def check_rectangle(rect, label, path):
    """A rectangle has whole-number x, y, w, h with a positive width and height."""
    if not isinstance(rect, dict):
        raise FileProblem(f"{path}: {label} must be a JSON object")
    for field in RECT_FIELDS:
        if not is_whole_number(rect.get(field)):
            raise FileProblem(f"{path}: {label} needs a whole number '{field}', got {rect.get(field)!r}")
    if rect["w"] <= 0 or rect["h"] <= 0:
        raise FileProblem(f"{path}: {label} must have a positive width and height")


def check_layout_shape(layout, path="layout"):
    """Rooms and hallway rectangles are complete enough for every check to run."""
    rooms = layout.get("rooms")
    if not isinstance(rooms, list):
        raise FileProblem(f"{path}: the layout needs a 'rooms' list")
    for i, room in enumerate(rooms):
        label = f"room {i + 1}"
        if isinstance(room, dict) and not isinstance(room.get("name"), str):
            raise FileProblem(f"{path}: {label} needs a 'name'")
        check_rectangle(room, f"{label} ({room.get('name')})" if isinstance(room, dict) else label, path)

    segments = layout.get("hallway_segments")
    if segments is not None:
        if not isinstance(segments, list):
            raise FileProblem(f"{path}: 'hallway_segments' must be a list")
        for i, segment in enumerate(segments):
            check_rectangle(segment, f"hallway segment {i + 1}", path)
    elif layout.get("hallway") is not None:
        check_rectangle(layout["hallway"], "hallway", path)


def check_input_shape(inp, path="input"):
    """The input has the fields the checks read. Bad values (entrance, names, ...) are left to I1."""
    if not isinstance(inp, dict):
        raise FileProblem(f"{path}: the input must be a JSON object")

    plot = inp.get("plot")
    if not (isinstance(plot, list) and len(plot) == 2 and all(is_whole_number(v) and v > 0 for v in plot)):
        raise FileProblem(f"{path}: 'plot' must be [width, length] in whole feet, got {plot!r}")

    setbacks = inp.get("setbacks", {})
    if not isinstance(setbacks, dict) or not all(is_whole_number(v) and v >= 0 for v in setbacks.values()):
        raise FileProblem(f"{path}: 'setbacks' must map sides to whole feet of 0 or more")

    rooms = inp.get("rooms", [])
    if not isinstance(rooms, list):
        raise FileProblem(f"{path}: 'rooms' must be a list")
    for i, room in enumerate(rooms):
        if not (isinstance(room, dict) and isinstance(room.get("name"), str) and isinstance(room.get("type"), str)):
            raise FileProblem(f"{path}: room {i + 1} needs a 'name' and a 'type'")

    pins = inp.get("pins", [])
    if not isinstance(pins, list) or not all(isinstance(p, dict) and "room" in p for p in pins):
        raise FileProblem(f"{path}: 'pins' must be a list of objects with a 'room'")


# ---------------------------------------------------------------------------
# Checking and reporting
# ---------------------------------------------------------------------------

def check_files(input_path, layout_path, layout_index=0, **validate_options):
    """Load both files and return validate_all's problem list.

    validate_options are passed on to validate_all (for example check_gaps=False).
    Raises FileProblem when a file cannot be used.
    """
    inp = load_input(input_path)
    layout = load_layout(layout_path, layout_index)
    try:
        return validate_all(inp, layout, **validate_options)
    except (KeyError, TypeError, ValueError, AttributeError) as e:  # safety net for shapes not caught above
        raise FileProblem(f"the checker could not read the files ({type(e).__name__}: {e})") from None


def format_problem(problem):
    return f"  [{problem['code']}] {problem['message']}"


def format_report(problems, input_path, layout_path):
    """Readable report: errors first, then warnings, then a one-line result."""
    errors, warnings = errors_only(problems), warnings_only(problems)
    lines = [f"Input:  {input_path}", f"Layout: {layout_path}", ""]
    for title, group in (("ERRORS", errors), ("WARNINGS", warnings)):
        if group:
            lines.append(f"{title} ({len(group)})")
            lines += [format_problem(p) for p in group]
            lines.append("")
    verdict = "NOT VALID" if errors else "VALID"
    lines.append(f"Result: {verdict} ({count(errors, 'error')}, {count(warnings, 'warning')})")
    return "\n".join(lines)


def count(items, word):
    """'1 error', '2 errors', '0 errors'."""
    return f"{len(items)} {word}{'' if len(items) == 1 else 's'}"


def json_report(problems, input_path, layout_path):
    return json.dumps({
        "input": str(input_path),
        "layout": str(layout_path),
        "valid": not errors_only(problems),
        "errors": errors_only(problems),
        "warnings": warnings_only(problems),
    }, indent=2)


def build_parser():
    parser = argparse.ArgumentParser(description="Check one floor plan layout against its input.")
    parser.add_argument("input", help="input JSON file (plain input or a test case file)")
    parser.add_argument("layout", help="layout JSON file (checker format, P1 solver result or P3 output)")
    parser.add_argument("--layout-index", type=int, default=0,
                        help="which layout to check when the file has a 'layouts' list (default 0)")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    return parser


def main(argv=None):
    """Run the command. Returns the exit code instead of exiting, so tests can call it."""
    args = build_parser().parse_args(argv)
    try:
        problems = check_files(args.input, args.layout, args.layout_index)
    except FileProblem as e:
        if args.json:
            print(json.dumps({"input": args.input, "layout": args.layout, "valid": False,
                              "file_problem": str(e)}, indent=2))
        else:
            print(f"FILE PROBLEM: {e}", file=sys.stderr)
        return EXIT_FILE_PROBLEM

    if args.json:
        print(json_report(problems, args.input, args.layout))
    else:
        print(format_report(problems, args.input, args.layout))
    return EXIT_INVALID if errors_only(problems) else EXIT_VALID


if __name__ == "__main__":
    sys.exit(main())