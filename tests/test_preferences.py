import pytest
from floorplan.preferences import (
    ZONE_MAP,
    calculate_zone_bounds,
    solve_with_preferences,
    generate_variants,
)


def test_zone_bounds_partitions_correctly():
    # Plot 30 x 30
    bounds_sw = calculate_zone_bounds(30, 30, "SW")
    assert bounds_sw["x_min"] == 0 and bounds_sw["x_max"] == 10
    assert bounds_sw["y_min"] == 0 and bounds_sw["y_max"] == 10

    bounds_mid = calculate_zone_bounds(30, 30, "Mid")
    assert bounds_mid["x_min"] == 10 and bounds_mid["x_max"] == 20
    assert bounds_mid["y_min"] == 10 and bounds_mid["y_max"] == 20

    bounds_ne = calculate_zone_bounds(30, 30, "NE")
    assert bounds_ne["x_min"] == 20 and bounds_ne["x_max"] == 30
    assert bounds_ne["y_min"] == 20 and bounds_ne["y_max"] == 30


def test_must_zone_constraint_h7():
    room_specs = {
        "Kitchen": {
            "min_width": 6,
            "max_width": 8,
            "min_height": 6,
            "max_height": 8,
        },
        "Living": {
            "min_width": 8,
            "max_width": 12,
            "min_height": 8,
            "max_height": 12,
        },
    }

    # Kitchen must be in SE (bottom-right: x in [20, 30], y in [0, 10])
    preferences = {
        "Kitchen": {"zone": "SE", "zone_mode": "must"}
    }

    result = solve_with_preferences(
        plot_width=30,
        plot_height=30,
        room_specs=room_specs,
        preferences=preferences,
    )

    assert result["status"] == "success"
    kitchen = result["rooms"]["Kitchen"]
    cx = kitchen["x"] + kitchen["width"] / 2
    cy = kitchen["y"] + kitchen["height"] / 2

    bounds = calculate_zone_bounds(30, 30, "SE")
    assert bounds["x_min"] <= cx <= bounds["x_max"]
    assert bounds["y_min"] <= cy <= bounds["y_max"]


def test_required_adjacency_h6():
    room_specs = {
        "Master": {
            "min_width": 8,
            "max_width": 10,
            "min_height": 8,
            "max_height": 10,
        },
        "Bath": {
            "min_width": 4,
            "max_width": 6,
            "min_height": 4,
            "max_height": 6,
        },
    }

    result = solve_with_preferences(
        plot_width=25,
        plot_height=25,
        room_specs=room_specs,
        required_adjacencies=[("Master", "Bath")],
    )

    assert result["status"] == "success"
    m = result["rooms"]["Master"]
    b = result["rooms"]["Bath"]

    # Check that they share a wall segment of >= 3 ft
    vert_touch = (m["x"] + m["width"] == b["x"]) or (b["x"] + b["width"] == m["x"])
    horiz_touch = (m["y"] + m["height"] == b["y"]) or (b["y"] + b["height"] == m["y"])
    assert vert_touch or horiz_touch

    if vert_touch:
        overlap_y = min(m["y"] + m["height"], b["y"] + b["height"]) - max(m["y"], b["y"])
        assert overlap_y >= 3
    if horiz_touch:
        overlap_x = min(m["x"] + m["width"], b["x"] + b["width"]) - max(m["x"], b["x"])
        assert overlap_x >= 3


def test_preferred_size_s1():
    room_specs = {
        "Room A": {
            "min_width": 6,
            "max_width": 12,
            "min_height": 6,
            "max_height": 12,
            "pref_width": 10,
            "pref_height": 10,
        }
    }

    result = solve_with_preferences(
        plot_width=20,
        plot_height=20,
        room_specs=room_specs,
    )

    assert result["status"] == "success"
    room = result["rooms"]["Room A"]
    # Solver should pick the preferred size when unconstrained
    assert room["width"] == 10
    assert room["height"] == 10


def test_entrance_side_s5():
    room_specs = {
        "living": {
            "min_width": 8,
            "max_width": 10,
            "min_height": 8,
            "max_height": 10,
        }
    }

    # Entrance on South (y=0)
    result_s = solve_with_preferences(
        plot_width=30,
        plot_height=30,
        room_specs=room_specs,
        entrance="S",
    )
    assert result_s["status"] == "success"
    assert result_s["rooms"]["living"]["y"] == 0

    # Entrance on North (top, y + height == 30)
    result_n = solve_with_preferences(
        plot_width=30,
        plot_height=30,
        room_specs=room_specs,
        entrance="N",
    )
    assert result_n["status"] == "success"
    liv_n = result_n["rooms"]["living"]
    assert liv_n["y"] + liv_n["height"] == 30


def test_edit_pin_and_locked_rooms_s6():
    room_specs = {
        "Living": {"min_width": 8, "max_width": 14, "min_height": 8, "max_height": 14},
        "Bed": {"min_width": 8, "max_width": 14, "min_height": 8, "max_height": 14},
    }

    initial = solve_with_preferences(
        plot_width=25,
        plot_height=25,
        room_specs=room_specs,
    )
    assert initial["status"] == "success"

    # User pins Bed width to 12 and locks Living in place
    living_pos = initial["rooms"]["Living"]
    re_solve = solve_with_preferences(
        plot_width=25,
        plot_height=25,
        room_specs=room_specs,
        locked_rooms={"Living": living_pos},
        pinned_dimensions={"Bed": {"width": 12}},
        previous_layout={k: {"x": v["x"], "y": v["y"]} for k, v in initial["rooms"].items()},
    )

    assert re_solve["status"] == "success"
    assert re_solve["rooms"]["Living"] == living_pos
    assert re_solve["rooms"]["Bed"]["width"] == 12


def test_generate_variants_produces_diverse_layouts():
    room_specs = {
        "Living": {"min_width": 6, "max_width": 10, "min_height": 6, "max_height": 10},
        "Kitchen": {"min_width": 6, "max_width": 8, "min_height": 6, "max_height": 8},
        "Bed": {"min_width": 6, "max_width": 8, "min_height": 6, "max_height": 8},
    }

    variants = generate_variants(
        count=3,
        plot_width=24,
        plot_height=24,
        room_specs=room_specs,
    )

    assert len(variants) >= 2
    for v in variants:
        assert v["status"] == "success"

    # Check that zone layouts differ
    first_zones = variants[0]["room_zones"]
    second_zones = variants[1]["room_zones"]
    diff_count = sum(1 for r in room_specs if first_zones.get(r) != second_zones.get(r))
    assert diff_count >= 2
