import copy

from floorplan.validator import (
    buildable_area,
    check_inside_plot,
    check_no_overlap,
    check_size_limits,
    validate,
)

# Same input as t01_standard: 30 x 40 plot, setbacks 5/3/3/3 -> buildable 24 x 32.
INPUT = {
    "plot": [30, 40],
    "setbacks": {"front": 5, "back": 3, "left": 3, "right": 3},
    "entrance": "S",
    "north": "up",
    "rooms": [
        {"name": "living", "type": "living"},
        {"name": "kitchen", "type": "kitchen", "zone": "SE", "zone_mode": "try"},
        {"name": "bedroom", "type": "bedroom", "zone": "NW", "zone_mode": "must"},
        {"name": "bathroom", "type": "bathroom"},
    ],
}

# A hand-made good layout. Not solver output.
GOOD = {
    "rooms": [
        {"name": "living", "x": 0, "y": 0, "w": 14, "h": 16},
        {"name": "kitchen", "x": 14, "y": 0, "w": 10, "h": 10},
        {"name": "bedroom", "x": 0, "y": 16, "w": 12, "h": 12},
        {"name": "bathroom", "x": 12, "y": 16, "w": 6, "h": 8},
    ],
}


def bad(**changes_by_room):
    """Copy of GOOD with some room fields changed, e.g. bad(kitchen={'x': 13})."""
    layout = copy.deepcopy(GOOD)
    for room in layout["rooms"]:
        room.update(changes_by_room.get(room["name"], {}))
    return layout


def test_buildable_area():
    assert buildable_area(INPUT) == (24, 32)


def test_good_layout_passes_everything():
    assert validate(INPUT, GOOD) == []


def test_inside_plot_catches_room_sticking_out_the_top():
    found = check_inside_plot(INPUT, bad(bedroom={"y": 24}))  # 24 + 12 = 36 > 32
    assert [v["rooms"] for v in found] == [["bedroom"]]
    assert found[0]["code"] == "H1"


def test_inside_plot_catches_negative_position():
    assert len(check_inside_plot(INPUT, bad(kitchen={"x": -1}))) == 1


def test_overlap_caught_when_kitchen_slides_into_living():
    found = check_no_overlap(bad(kitchen={"x": 13}))
    assert len(found) == 1
    assert set(found[0]["rooms"]) == {"living", "kitchen"}


def test_touching_edges_is_not_overlap():
    assert check_no_overlap(GOOD) == []


def test_size_below_minimum_caught():
    found = check_size_limits(INPUT, bad(bathroom={"w": 4, "h": 6}))
    assert len(found) == 1
    assert "below its minimum" in found[0]["message"]


def test_size_above_maximum_caught():
    found = check_size_limits(INPUT, bad(kitchen={"w": 13}))
    assert len(found) == 1
    assert "above its maximum" in found[0]["message"]


def test_room_turned_90_degrees_is_fine():
    assert check_size_limits(INPUT, bad(bathroom={"w": 8, "h": 6})) == []


def test_pinned_width_must_hold():
    pinned = {**INPUT, "pins": [{"room": "bedroom", "width": 14}]}
    assert len(check_size_limits(pinned, GOOD)) == 1  # bedroom is 12 wide
    assert check_size_limits(pinned, bad(bedroom={"w": 14})) == []


def test_unknown_room_in_layout_caught():
    layout = copy.deepcopy(GOOD)
    layout["rooms"].append({"name": "ghost", "x": 20, "y": 20, "w": 4, "h": 4})
    found = check_size_limits(INPUT, layout)
    assert found and found[0]["rooms"] == ["ghost"]


def test_hallway_is_checked_for_inside_and_overlap():
    layout = copy.deepcopy(GOOD)
    layout["hallway"] = {"x": 20, "y": 28, "w": 4, "h": 6}  # top is 34 > 32
    assert len(check_inside_plot(INPUT, layout)) == 1
    layout["hallway"] = {"x": 10, "y": 0, "w": 4, "h": 10}  # sits inside living
    assert len(check_no_overlap(layout)) == 1


def test_unknown_room_type_gives_a_clear_message_not_a_crash():
    inp = {**INPUT, "rooms": INPUT["rooms"] + [{"name": "balcony1", "type": "balcony"}]}
    layout = copy.deepcopy(GOOD)
    layout["rooms"].append({"name": "balcony1", "x": 18, "y": 16, "w": 4, "h": 4})
    found = check_size_limits(inp, layout)
    assert len(found) == 1
    assert "no size rule for room type 'balcony'" in found[0]["message"]
