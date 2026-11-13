"""Check one saved layout against its input from the command line (P4).

    python validate_file.py input.json layout.json
    python validate_file.py input.json layout.json --json
    python validate_file.py input.json p3_output.json --layout-index 1
    python validate_file.py input.json saved_api_output.json --coords plot

Input file: a plain input, or a test case file {"name", "input", "expect"} (the "input" part is used).
Layout file, any of:
  - the checker format: {"rooms": [ ... ], "hallway_segments": [ ... ]}
  - P1's raw solver result: {"status": "success", "rooms": {name: {...}}, ...}
  - P3's output: {"layouts": [layout, ...]} (pick one with --layout-index, default 0)

Coordinates: the checker works in buildable coordinates, (0, 0) at the bottom-left of the buildable area.
Layouts saved from the public API may use plot coordinates, (0, 0) at the bottom-left of the whole plot.
Which one a file uses is decided in this order:
  1. the --coords option, if given;
  2. otherwise a "coordinate_system" field in the chosen layout, or else at the top of the file;
  3. otherwise "buildable", so older files and commands keep working.
Plot coordinates are converted to buildable before checking (agreed with P1, 2026-11-11):
  buildable_x = plot_x - setbacks.left, buildable_y = plot_y - setbacks.front
Front is always the bottom edge, whatever the entrance or north. A missing side counts as 0.
The conversion is written here on purpose instead of importing P3's coordinates.py, so a mistake in one
cannot hide in both. validate_all itself only ever sees buildable coordinates.

Exit codes: 0 valid (warnings allowed), 1 the layout has errors, 2 a file could not be read or understood.
The same checks are available from Python with check_files(input_path, layout_path).
"""
import argparse
import copy
import json
import math
import sys

from validate_all import adapt_solver_result, errors_only, validate_all, warnings_only

EXIT_VALID = 0
EXIT_INVALID = 1
EXIT_FILE_PROBLEM = 2

RECT_FIELDS = ("x", "y", "w", "h")
SOLVER_SUCCESS = "success"

BUILDABLE = "buildable"
PLOT = "plot"
COORDINATE_SYSTEMS = (BUILDABLE, PLOT)
COORDINATE_MARKER = "coordinate_system"
SETBACK_SIDES = ("front", "back", "left", "right")
# Layout parts that carry positions. Sizes (w, h) and pins never change with the coordinate system.
POSITIONED_LISTS = ("rooms", "hallway_segments", "doors", "windows")


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
    """The input dict from a plain input file or from a test case file.

    "setbacks": null means no setbacks (all sides 0), the same as leaving the field out.
    """
    data = read_json(path)
    if isinstance(data, dict) and isinstance(data.get("input"), dict):
        data = data["input"]
    check_input_shape(data, path)
    if data.get("setbacks", {}) is None:
        data = {**data, "setbacks": {}}
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
        try:
            layout = adapt_solver_result(data)
        except ValueError as e:
            raise FileProblem(f"{path}: {e}") from None
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

    # Doors and windows are not checked by validate_all yet, but they carry positions that must be
    # converted between coordinate systems, so their shape is checked here.
    check_positions(layout, "doors", "door", required=("x", "y"), optional=(), path=path)
    check_positions(layout, "windows", "window", required=("x",), optional=("y",), path=path)


def is_number(value):
    """True for a finite int or float (bool is excluded). Doors and windows may sit at fractions of a foot."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def describe(item):
    """A short label for a door or window in error messages, e.g. '(living / hallway_1)'."""
    if not isinstance(item, dict):
        return ""
    if isinstance(item.get("between"), list):
        return f" ({' / '.join(str(name) for name in item['between'])})"
    if item.get("room") is not None:
        return f" ({item['room']}, {item.get('wall', '?')} wall)"
    return ""


def check_positions(layout, key, label, required, optional, path):
    """layout[key] is missing, null or a list of objects whose position fields are numbers.

    required fields must be present; optional fields may be left out, but not given as null or text.
    """
    items = layout.get(key)
    if items is None:
        return
    if not isinstance(items, list):
        raise FileProblem(f"{path}: '{key}' must be a list, got {type(items).__name__}")
    for i, item in enumerate(items):
        name = f"{label} {i + 1}{describe(item)}"
        if not isinstance(item, dict):
            raise FileProblem(f"{path}: {name} must be a JSON object")
        for field in required:
            if not is_number(item.get(field)):
                raise FileProblem(f"{path}: {name} needs a number '{field}', got {item.get(field)!r}")
        for field in optional:
            if field in item and not is_number(item[field]):
                raise FileProblem(f"{path}: {name} has '{field}' {item[field]!r}, it must be a number")


def check_input_shape(inp, path="input"):
    """The input has the fields the checks read. Bad values (entrance, names, ...) are left to I1."""
    if not isinstance(inp, dict):
        raise FileProblem(f"{path}: the input must be a JSON object")

    plot = inp.get("plot")
    if not (isinstance(plot, list) and len(plot) == 2 and all(is_whole_number(v) and v > 0 for v in plot)):
        raise FileProblem(f"{path}: 'plot' must be [width, length] in whole feet, got {plot!r}")

    setbacks = inp.get("setbacks")
    if setbacks is None:  # missing or null: no setbacks at all
        setbacks = {}
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
# Coordinate systems: plot <-> buildable
# ---------------------------------------------------------------------------

def setback_offsets(inp, path="input"):
    """(left, front) setbacks in feet: how far the buildable area's (0, 0) is from the plot's (0, 0).

    A missing or null setbacks object means all sides are 0, and a missing side counts as 0.
    A side given as null, a non-whole number or a negative number is a file problem (the same rule as
    P3's conversion utility).
    """
    setbacks = inp.get("setbacks")
    if setbacks is None:
        return 0, 0
    if not isinstance(setbacks, dict):
        raise FileProblem(f"{path}: 'setbacks' must be an object")
    for side in SETBACK_SIDES:
        if side in setbacks and not (is_whole_number(setbacks[side]) and setbacks[side] >= 0):
            raise FileProblem(f"{path}: setback '{side}' must be a whole number of 0 or more, got {setbacks[side]!r}")
    return setbacks.get("left", 0), setbacks.get("front", 0)


def shift_layout(layout, dx, dy):
    """A copy of layout with every position moved by (dx, dy). The original is not changed.

    Moves x and y of rooms, hallway segments (and a legacy single hallway), doors and windows.
    Anything without a numeric x or y (for example a window given only by its wall) keeps that field.
    """
    shifted = copy.deepcopy(layout)
    items = [item for key in POSITIONED_LISTS for item in (shifted.get(key) or []) if isinstance(item, dict)]
    if isinstance(shifted.get("hallway"), dict):
        items.append(shifted["hallway"])
    for item in items:
        for field, delta in (("x", dx), ("y", dy)):
            value = item.get(field)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                item[field] = value + delta
    return shifted


def plot_to_buildable(layout, inp):
    """buildable_x = plot_x - left setback, buildable_y = plot_y - front setback."""
    left, front = setback_offsets(inp)
    return shift_layout(layout, -left, -front)


def buildable_to_plot(layout, inp):
    """plot_x = buildable_x + left setback, plot_y = buildable_y + front setback."""
    left, front = setback_offsets(inp)
    return shift_layout(layout, left, front)


def marker_in_file(data, layout_index=0):
    """The coordinate_system field of the chosen layout, or else of the whole file, or None."""
    if not isinstance(data, dict):
        return None
    layouts = data.get("layouts")
    if isinstance(layouts, list) and 0 <= layout_index < len(layouts) and isinstance(layouts[layout_index], dict):
        if COORDINATE_MARKER in layouts[layout_index]:
            return layouts[layout_index][COORDINATE_MARKER]
    return data.get(COORDINATE_MARKER)


def choose_coordinate_system(option, marker, path="layout"):
    """(system, source): the --coords option wins, then the file's marker, then buildable."""
    if option is not None:
        system, source = option, "--coords option"
    elif marker is not None:
        system, source = marker, f"'{COORDINATE_MARKER}' in the file"
    else:
        return BUILDABLE, "default"
    if system not in COORDINATE_SYSTEMS:
        raise FileProblem(f"{path}: coordinate system must be one of {', '.join(COORDINATE_SYSTEMS)}, "
                          f"got {system!r} (from the {source})")
    return system, source


# ---------------------------------------------------------------------------
# Checking and reporting
# ---------------------------------------------------------------------------

def load_case(input_path, layout_path, layout_index=0, coords=None):
    """(input, layout in buildable coordinates, coordinate system used, where that choice came from)."""
    inp = load_input(input_path)
    data = read_json(layout_path)
    system, source = choose_coordinate_system(coords, marker_in_file(data, layout_index), layout_path)
    layout = to_layout(data, layout_path, layout_index)
    if system == PLOT:
        layout = plot_to_buildable(layout, inp)
    return inp, layout, system, source


def check_files(input_path, layout_path, layout_index=0, coords=None, **validate_options):
    """Load both files and return validate_all's problem list.

    coords is "buildable", "plot" or None (use the file's marker, else buildable).
    validate_options are passed on to validate_all (for example check_gaps=False).
    Raises FileProblem when a file cannot be used.
    """
    inp, layout, _, _ = load_case(input_path, layout_path, layout_index, coords)
    return run_checker(inp, layout, **validate_options)


def run_checker(inp, layout, **validate_options):
    try:
        return validate_all(inp, layout, **validate_options)
    except (KeyError, TypeError, ValueError, AttributeError) as e:  # safety net for shapes not caught above
        raise FileProblem(f"the checker could not read the files ({type(e).__name__}: {e})") from None


def format_problem(problem):
    return f"  [{problem['code']}] {problem['message']}"


def format_report(problems, input_path, layout_path, coordinates=None):
    """Readable report: errors first, then warnings, then a one-line result.

    coordinates is an optional (system, source) pair, shown under the file names.
    """
    errors, warnings = errors_only(problems), warnings_only(problems)
    lines = [f"Input:  {input_path}", f"Layout: {layout_path}"]
    if coordinates:
        lines.append(f"Coordinates: {coordinates[0]} (from the {coordinates[1]})")
    lines.append("")
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


def json_report(problems, input_path, layout_path, coordinates=None):
    report = {
        "input": str(input_path),
        "layout": str(layout_path),
        "valid": not errors_only(problems),
        "errors": errors_only(problems),
        "warnings": warnings_only(problems),
    }
    if coordinates:
        report["coordinate_system"], report["coordinate_source"] = coordinates
    return json.dumps(report, indent=2)


def build_parser():
    parser = argparse.ArgumentParser(description="Check one floor plan layout against its input.")
    parser.add_argument("input", help="input JSON file (plain input or a test case file)")
    parser.add_argument("layout", help="layout JSON file (checker format, P1 solver result or P3 output)")
    parser.add_argument("--layout-index", type=int, default=0,
                        help="which layout to check when the file has a 'layouts' list (default 0)")
    parser.add_argument("--coords", choices=COORDINATE_SYSTEMS, default=None,
                        help="coordinate system of the layout file; overrides its 'coordinate_system' field "
                             "(default: that field, else buildable)")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    return parser


def main(argv=None):
    """Run the command. Returns the exit code instead of exiting, so tests can call it."""
    args = build_parser().parse_args(argv)
    try:
        inp, layout, system, source = load_case(args.input, args.layout, args.layout_index, args.coords)
        problems = run_checker(inp, layout)
    except FileProblem as e:
        if args.json:
            print(json.dumps({"input": args.input, "layout": args.layout, "valid": False,
                              "file_problem": str(e)}, indent=2))
        else:
            print(f"FILE PROBLEM: {e}", file=sys.stderr)
        return EXIT_FILE_PROBLEM

    if args.json:
        print(json_report(problems, args.input, args.layout, (system, source)))
    else:
        print(format_report(problems, args.input, args.layout, (system, source)))
    return EXIT_INVALID if errors_only(problems) else EXIT_VALID


if __name__ == "__main__":
    sys.exit(main())
