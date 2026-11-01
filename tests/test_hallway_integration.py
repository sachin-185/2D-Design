from floorplan.geometry import solve_layout


def test_hallway_adjacency_solver_finds_layout():

    room_specs = {
        "living_room": {
            "min_width": 8,
            "max_width": 12,
            "min_height": 8,
            "max_height": 12,
        },
        "kitchen": {
            "min_width": 6,
            "max_width": 10,
            "min_height": 6,
            "max_height": 10,
        },
        "bedroom_1": {
            "min_width": 8,
            "max_width": 12,
            "min_height": 8,
            "max_height": 12,
        },
        "bathroom_1": {
            "min_width": 5,
            "max_width": 8,
            "min_height": 5,
            "max_height": 8,
        },
    }

    layout_input = {
        "rooms": [
            {"name": "living_room", "type": "living"},
            {"name": "kitchen", "type": "kitchen"},
            {"name": "bedroom_1", "type": "bedroom"},
            {"name": "bathroom_1", "type": "bathroom"},
        ]
    }

    result = solve_layout(
        plot_width=30,
        plot_height=24,
        room_specs=room_specs,
        setbacks={
            "left": 0,
            "right": 0,
            "front": 0,
            "back": 0,
        },
        include_hallway=True,
        layout_input=layout_input,
        max_hallway_segments=2,
        time_limit_seconds=60,
    )

    assert result["status"] == "success"

def test_living_room_touches_south_entrance_boundary():

    room_specs = {
        "living_room": {
            "min_width": 8,
            "max_width": 12,
            "min_height": 8,
            "max_height": 12,
        },
        "kitchen": {
            "min_width": 6,
            "max_width": 10,
            "min_height": 6,
            "max_height": 10,
        },
        "bedroom_1": {
            "min_width": 8,
            "max_width": 12,
            "min_height": 8,
            "max_height": 12,
        },
        "bathroom_1": {
            "min_width": 5,
            "max_width": 8,
            "min_height": 5,
            "max_height": 8,
        },
    }

    layout_input = {
        "entrance": "S",
        "north": "up",
        "rooms": [
            {"name": "living_room", "type": "living"},
            {"name": "kitchen", "type": "kitchen"},
            {"name": "bedroom_1", "type": "bedroom"},
            {"name": "bathroom_1", "type": "bathroom"},
        ],
    }

    result = solve_layout(
        plot_width=30,
        plot_height=24,
        room_specs=room_specs,
        include_hallway=True,
        layout_input=layout_input,
        max_hallway_segments=2,
        time_limit_seconds=60,
    )

    assert result["status"] == "success"

    living = result["rooms"]["living_room"]

    assert living["y"] == 0

def test_rooms_and_hallway_cover_buildable_area():

    room_specs = {
        "living_room": {
            "min_width": 8,
            "max_width": 12,
            "min_height": 8,
            "max_height": 12,
        }
    }

    layout_input = {
        "entrance": "S",
        "north": "up",
        "rooms": [
            {"name": "living_room", "type": "living"},
        ],
    }

    result = solve_layout(
        plot_width=12,
        plot_height=12,
        room_specs=room_specs,
        include_hallway=True,
        layout_input=layout_input,
        require_full_coverage=True,
    )

    assert result["status"] == "success"

    rooms_area = sum(
        room["area"]
        for room in result["rooms"].values()
    )

    hallway_area = result["hallway"]["area"]

    total_area = rooms_area + hallway_area

    buildable_area = (
        result["buildable_width"] *
        result["buildable_depth"]
    )

    assert total_area == buildable_area