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
    )

    assert result["status"] == "success"

    living = result["rooms"]["living_room"]

    assert living["y"] == 0