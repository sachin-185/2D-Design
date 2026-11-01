
from floorplan.connections_check import check_no_5x5_hallway_square


def make_layout(halls):
    return {
        "rooms": [],
        "hallway_segments": halls
    }

def test_rejects_10_by_7_hallway():
    layout = make_layout([
        {"name": "hallway_1", "x": 8, "y": 21, "w": 10, "h": 3},
        {"name": "hallway_2", "x": 8, "y": 17, "w": 10, "h": 4},
    ])

    assert check_no_5x5_hallway_square(layout)


def test_accepts_4_by_12_corridor():
    layout = make_layout([
        {"name": "hallway_1", "x": 0, "y": 0, "w": 12, "h": 4},
    ])

    assert check_no_5x5_hallway_square(layout) == []


def test_rejects_square_created_by_multiple_segments():
    layout = make_layout([
        {"name": "hallway_1", "x": 0, "y": 0, "w": 5, "h": 3},
        {"name": "hallway_2", "x": 0, "y": 3, "w": 5, "h": 2},
    ])

    assert check_no_5x5_hallway_square(layout)


def test_accepts_l_shaped_corridor():
    layout = make_layout([
        {"name": "hallway_1", "x": 0, "y": 0, "w": 12, "h": 4},
        {"name": "hallway_2", "x": 8, "y": 4, "w": 4, "h": 8},
    ])

    assert check_no_5x5_hallway_square(layout) == []


def test_accepts_t_shaped_corridor():
    layout = make_layout([
        {"name": "hallway_1", "x": 0, "y": 0, "w": 12, "h": 4},
        {"name": "hallway_2", "x": 4, "y": 4, "w": 4, "h": 8},
    ])

    assert check_no_5x5_hallway_square(layout) == []


def test_no_hallways():
    assert check_no_5x5_hallway_square({"rooms": []}) == []
