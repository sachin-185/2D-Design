
from floorplan.connections import required_pairs, HALLWAY


def test_attached_bathroom_connects_to_bedroom():
    inp = {
        "rooms": [
            {"name": "living", "type": "living"},
            {"name": "bedroom_1", "type": "bedroom"},
            {
                "name": "bath_1",
                "type": "bathroom",
                "attached_to": "bedroom_1",
            },
            {"name": "common_bath", "type": "bathroom"},
        ]
    }

    assert required_pairs(inp) == [
        ("living", HALLWAY),
        ("bedroom_1", HALLWAY),
        ("bath_1", "bedroom_1"),
        ("common_bath", HALLWAY),
    ]


def test_two_attached_bathrooms_to_same_bedroom():
    inp = {
        "rooms": [
            {"name": "living", "type": "living"},
            {"name": "bedroom_1", "type": "bedroom"},
            {
                "name": "bath_1",
                "type": "bathroom",
                "attached_to": "bedroom_1",
            },
            {
                "name": "bath_2",
                "type": "bathroom",
                "attached_to": "bedroom_1",
            },
        ]
    }

    pairs = required_pairs(inp)

    assert ("bath_1", "bedroom_1") in pairs
    assert ("bath_2", "bedroom_1") in pairs
    assert ("bath_1", HALLWAY) not in pairs
    assert ("bath_2", HALLWAY) not in pairs
