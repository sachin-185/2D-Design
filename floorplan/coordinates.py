
"""
Coordinate conversion utilities for the floorplan engine.

Internal coordinate system:
    (0, 0) = bottom-left corner of the buildable area.

Public coordinate system:
    (0, 0) = bottom-left corner of the entire plot.

The solver, engine, and checker continue using buildable coordinates.
Only the API boundary should use these conversion functions.
"""

import math


# Fields containing objects whose absolute positions must be shifted.
POSITIONED_LISTS = (
    "rooms",
    "hallway_segments",
    "doors",
    "windows",
)

SETBACK_SIDES = ("left", "right", "front", "back")


def _is_number(value):
    """Accept finite integers and floats, but reject booleans."""
    if isinstance(value, bool):
        return False

    if isinstance(value, int):
        return True

    if isinstance(value, float):
        return math.isfinite(value)

    return False


def _validate_number(value, label):
    """Validate a coordinate or setback value."""
    if not _is_number(value):
        raise ValueError(f"{label} must be a finite number. Got {value!r}.")


def _normalise_number(value):
    """Keep whole-number results as integers and preserve fractions."""
    if isinstance(value, float) and value.is_integer():
        return int(value)

    return value


def plot_origin(setbacks):
    """
    Return the buildable area's origin within the plot.

    Returns:
        (left, front)

    Rules:
        - Missing setback object means all setbacks are zero.
        - Missing individual sides default to zero.
        - Explicitly supplied None values are invalid.
    """
    if setbacks is None:
        setbacks = {}

    if not isinstance(setbacks, dict):
        raise ValueError("Setbacks must be a dictionary or None.")

    values = {}

    for side in SETBACK_SIDES:
        value = setbacks.get(side, 0)
        _validate_number(value, f"Setbacks.{side}")

        if type(value) is not int or value < 0:
            raise ValueError(
                f"Setbacks.{side} must be a non-negative integer. Got {value!r}."
            )
        
        values[side] = value

    return values["left"], values["front"]


def _shift_coordinate(value, offset, direction, label):
    """Shift one coordinate while preserving integer and fractional values."""
    _validate_number(value, label)

    if direction == "to_plot":
        result = value + offset
    elif direction == "to_buildable":
        result = value - offset
    else:
        raise ValueError(f"Unsupported conversion direction: {direction}")

    return _normalise_number(result)


def _shift_object(obj, x_offset, y_offset, direction, label):
    """
    Return a shifted copy of one positioned object.

    Only x and y are shifted.
    Dimensions and all other metadata remain unchanged.
    """
    if not isinstance(obj, dict):
        raise ValueError(f"{label} must be a dictionary.")

    shifted = dict(obj)

    # Both coordinates are required for rooms, hallways and doors.
    for field, offset in (("x", x_offset), ("y", y_offset)):
        if field not in obj:
            raise ValueError(f"{label} is missing required coordinate '{field}'.")

        shifted[field] = _shift_coordinate(
            obj[field],
            offset,
            direction,
            f"{label}.{field}",
        )

    return shifted


def _shift_window(window, x_offset, y_offset, direction, label):
    """
    Shift a window's absolute position.

    Window x is required.
    Window y is optional. If present with None, it remains None.
    """
    if not isinstance(window, dict):
        raise ValueError(f"{label} must be a dictionary.")

    shifted = dict(window)

    if "x" not in window:
        raise ValueError(f"{label} is missing required coordinate 'x'.")

    shifted["x"] = _shift_coordinate(
        window["x"],
        x_offset,
        direction,
        f"{label}.x",
    )

    if "y" in window and window["y"] is not None:
        shifted["y"] = _shift_coordinate(
            window["y"],
            y_offset,
            direction,
            f"{label}.y",
        )

    return shifted


def _convert_layout(layout, setbacks, direction):
    """
    Convert a layout between buildable and plot coordinates.

    Supported positioned objects:
        - rooms
        - hallway_segments
        - legacy singular hallway
        - doors
        - windows

    The original layout is never modified.
    """
    if not isinstance(layout, dict):
        raise ValueError("Layout must be a dictionary.")

    left, front = plot_origin(setbacks)

    # Copy the top-level dictionary. Nested objects are copied as they
    # are converted, so the caller's original layout remains unchanged.
    converted = dict(layout)

    # Rooms must use the API list format.
    if "rooms" in layout:
        rooms = layout["rooms"]

        if not isinstance(rooms, list):
            raise ValueError(
                "'rooms' must be a list of room dictionaries. "
                "Raw dictionary-of-rooms solver output is not supported."
            )

        converted["rooms"] = [
            _shift_object(
                room,
                left,
                front,
                direction,
                f"room[{index}]",
            )
            for index, room in enumerate(rooms)
        ]

    # Convert each supported list of positioned objects.
    for field in POSITIONED_LISTS:
        if field not in layout:
            continue

        if field == "rooms":
            continue

        items = layout[field]

        if not isinstance(items, list):
            raise ValueError(f"'{field}' must be a list.")

        if field == "windows":
            converted[field] = [
                _shift_window(
                    item,
                    left,
                    front,
                    direction,
                    f"window[{index}]",
                )
                for index, item in enumerate(items)
            ]
        else:
            converted[field] = [
                _shift_object(
                    item,
                    left,
                    front,
                    direction,
                    f"{field}[{index}]",
                )
                for index, item in enumerate(items)
            ]

    # Backward compatibility for the old singular hallway format.
    if "hallway" in layout and layout["hallway"] is not None:
        converted["hallway"] = _shift_object(
            layout["hallway"],
            left,
            front,
            direction,
            "hallway",
        )

    return converted


def to_plot_coordinates(layout, setbacks):
    """
    Convert a buildable-coordinate layout to plot coordinates.

    plot_x = buildable_x + left_setback
    plot_y = buildable_y + front_setback
    """
    return _convert_layout(layout, setbacks, "to_plot")


def to_buildable_coordinates(layout, setbacks):
    """
    Convert a plot-coordinate layout to buildable coordinates.

    buildable_x = plot_x - left_setback
    buildable_y = plot_y - front_setback
    """
    return _convert_layout(layout, setbacks, "to_buildable")
