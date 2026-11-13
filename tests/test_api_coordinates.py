from copy import deepcopy

from fastapi.testclient import TestClient
from floorplan import api as api_module


# ---------------------------------------------------------
# SHARED TEST HELPERS
# ---------------------------------------------------------

def make_payload(
    setbacks=None,
    rooms=None,
    hallway_segments=None,
    doors=None,
    windows=None,
):
    if setbacks is None:
        setbacks = {
            "left": 3,
            "right": 2,
            "front": 4,
            "back": 1,
        }

    if rooms is None:
        rooms = [
            {
                "name": "living_room",
                "type": "living",
                "x": 3,
                "y": 4,
                "w": 8,
                "h": 6,
            }
        ]

    return {
        "input": {
            "plot": [40, 30],
            "setbacks": setbacks,
            "entrance": "S",
            "north": "up",
            "rooms": [
                {"name": room["name"], "type": room["type"]}
                for room in rooms
            ],
            "pins": [],
        },
        "layout": {
            "rooms": deepcopy(rooms),
            "hallway_segments": deepcopy(hallway_segments or []),
            "doors": deepcopy(doors or []),
            "windows": deepcopy(windows or []),
        },
    }


def render_with_mock(monkeypatch, payload):
    captured = {}

    def mock_renderer(layout, plot, setbacks, entrance):
        captured["layout"] = layout
        captured["plot"] = plot
        captured["setbacks"] = setbacks
        captured["entrance"] = entrance
        return "<svg>test</svg>"

    monkeypatch.setattr(
        api_module,
        "render_layout_to_svg",
        mock_renderer,
    )

    client = TestClient(api_module.app)
    response = client.post("/render", json=payload)

    return response, captured


# ---------------------------------------------------------
# TEST 1: BASIC COORDINATE CONVERSION
# ---------------------------------------------------------

def test_render_converts_plot_coordinates_to_buildable_before_rendering(
    monkeypatch,
):
    payload = make_payload()

    response, captured = render_with_mock(monkeypatch, payload)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")

    room = captured["layout"]["rooms"][0]

    assert room["x"] == 0
    assert room["y"] == 0

    assert captured["plot"] == (40, 30)
    assert captured["setbacks"]["left"] == 3
    assert captured["setbacks"]["front"] == 4
    assert captured["entrance"] == "S"

    assert response.text == "<svg>test</svg>"


# ---------------------------------------------------------
# TEST 2: ZERO SETBACKS
# ---------------------------------------------------------

def test_render_preserves_coordinates_when_setbacks_are_zero(
    monkeypatch,
):
    rooms = [
        {
            "name": "living_room",
            "type": "living",
            "x": 5,
            "y": 7,
            "w": 10,
            "h": 8,
        }
    ]

    payload = make_payload(
        setbacks={
            "left": 0,
            "right": 0,
            "front": 0,
            "back": 0,
        },
        rooms=rooms,
    )

    response, captured = render_with_mock(monkeypatch, payload)

    assert response.status_code == 200

    room = captured["layout"]["rooms"][0]

    assert room["x"] == 5
    assert room["y"] == 7


# ---------------------------------------------------------
# TEST 3: ASYMMETRIC SETBACKS
# ---------------------------------------------------------

def test_render_uses_asymmetric_setbacks(monkeypatch):
    rooms = [
        {
            "name": "living_room",
            "type": "living",
            "x": 7,
            "y": 9,
            "w": 10,
            "h": 8,
        }
    ]

    payload = make_payload(
        setbacks={
            "left": 3,
            "right": 5,
            "front": 4,
            "back": 2,
        },
        rooms=rooms,
    )

    response, captured = render_with_mock(monkeypatch, payload)

    assert response.status_code == 200

    room = captured["layout"]["rooms"][0]

    assert room["x"] == 4
    assert room["y"] == 5


# ---------------------------------------------------------
# TEST 4: MULTIPLE ROOMS
# ---------------------------------------------------------

def test_render_converts_multiple_rooms(monkeypatch):
    rooms = [
        {
            "name": "living_room",
            "type": "living",
            "x": 3,
            "y": 4,
            "w": 10,
            "h": 8,
        },
        {
            "name": "bedroom",
            "type": "bedroom",
            "x": 13,
            "y": 10,
            "w": 8,
            "h": 7,
        },
        {
            "name": "kitchen",
            "type": "kitchen",
            "x": 8,
            "y": 18,
            "w": 9,
            "h": 6,
        },
    ]

    payload = make_payload(rooms=rooms)

    response, captured = render_with_mock(monkeypatch, payload)

    assert response.status_code == 200

    converted_rooms = captured["layout"]["rooms"]

    assert len(converted_rooms) == 3

    assert (converted_rooms[0]["x"], converted_rooms[0]["y"]) == (0, 0)
    assert (converted_rooms[1]["x"], converted_rooms[1]["y"]) == (10, 6)
    assert (converted_rooms[2]["x"], converted_rooms[2]["y"]) == (5, 14)


# ---------------------------------------------------------
# TEST 5: HALLWAY SEGMENTS
# ---------------------------------------------------------

def test_render_converts_hallway_segments(monkeypatch):
    hallway_segments = [
        {
            "id": "hallway_1",
            "x": 8,
            "y": 4,
            "w": 3,
            "h": 12,
        }
    ]

    payload = make_payload(hallway_segments=hallway_segments)

    response, captured = render_with_mock(monkeypatch, payload)

    assert response.status_code == 200

    hallway = captured["layout"]["hallway_segments"][0]

    assert hallway["x"] == 5
    assert hallway["y"] == 0
    assert hallway["w"] == 3
    assert hallway["h"] == 12


# ---------------------------------------------------------
# TEST 6: DOORS AND WINDOWS
# ---------------------------------------------------------

def test_render_converts_doors_and_windows(monkeypatch):
    doors = [
        {
            "id": "door_1",
            "x": 5,
            "y": 4,
            "width": 3,
            "between": ["living_room", "hallway_1"],
        }
    ]

    windows = [
        {
            "id": "window_1",
            "x": 7,
            "y": 10,
            "width": 4,
            "room": "living_room",
            "wall": "N",
        }
    ]

    payload = make_payload(
        doors=doors,
        windows=windows,
    )

    response, captured = render_with_mock(monkeypatch, payload)

    assert response.status_code == 200

    door = captured["layout"]["doors"][0]
    window = captured["layout"]["windows"][0]

    assert door["x"] == 0.5
    assert door["y"] == 0
    assert door["width"] == 3

    assert window["x"] == 4
    assert window["y"] == 6


# ---------------------------------------------------------
# TEST 7: DIMENSIONS MUST REMAIN UNCHANGED
# ---------------------------------------------------------

def test_render_preserves_room_dimensions(monkeypatch):
    rooms = [
        {
            "name": "living_room",
            "type": "living",
            "x": 8,
            "y": 9,
            "w": 12,
            "h": 10,
        }
    ]

    payload = make_payload(rooms=rooms)

    response, captured = render_with_mock(monkeypatch, payload)

    assert response.status_code == 200

    room = captured["layout"]["rooms"][0]

    assert room["w"] == 12
    assert room["h"] == 10


# ---------------------------------------------------------
# TEST 8: ORIGINAL LAYOUT MUST NOT BE MODIFIED
# ---------------------------------------------------------

def test_render_does_not_modify_original_layout(monkeypatch):
    payload = make_payload()

    original_payload = deepcopy(payload)

    response, captured = render_with_mock(monkeypatch, payload)

    assert response.status_code == 200

    assert payload == original_payload

    # Conversion should not modify the original input layout.
    assert captured["layout"]["rooms"][0]["x"] == 0
    assert payload["layout"]["rooms"][0]["x"] == 3


# ---------------------------------------------------------
# TEST 9: PLOT AND SETBACK METADATA
# ---------------------------------------------------------

def test_render_preserves_plot_and_setbacks(monkeypatch):
    payload = make_payload()

    response, captured = render_with_mock(monkeypatch, payload)

    assert response.status_code == 200

    assert captured["plot"] == (40, 30)

    assert captured["setbacks"] == {
        "left": 3,
        "right": 2,
        "front": 4,
        "back": 1,
    }

    assert captured["entrance"] == "S"


# ---------------------------------------------------------
# TEST 10: SVG RESPONSE
# ---------------------------------------------------------

def test_render_returns_svg_content(monkeypatch):
    payload = make_payload()

    response, captured = render_with_mock(monkeypatch, payload)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text == "<svg>test</svg>"

