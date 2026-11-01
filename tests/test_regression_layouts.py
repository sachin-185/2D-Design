
import json
from pathlib import Path

from validate_all import validate_solver_result


REGRESSION_DIR = Path(__file__).parent / "regression"

INPUT = {
    "plot": [30, 24],
    "setbacks": {
        "left": 0,
        "right": 0,
        "front": 0,
        "back": 0,
    },
    "entrance": "S",
    "north": "up",
    "rooms": [
        {"name": "living", "type": "living"},
        {"name": "bedroom_1", "type": "bedroom"},
        {"name": "kitchen", "type": "kitchen"},
        {"name": "bathroom", "type": "bathroom"},
    ],
}


def load_layout(filename):
    file_path = REGRESSION_DIR / filename

    with open(file_path, "r") as file:
        return json.load(file)


def test_previous_30x24_layout():
    layout = load_layout("previous_30x24_layout.json")

    issues = validate_solver_result(INPUT, layout)

    assert issues == [], f"Previous layout failed: {issues}"


def test_latest_30x24_layout():
    layout = load_layout("latest_30x24_layout.json")

    issues = validate_solver_result(INPUT, layout)

    assert issues == [], f"Latest layout failed: {issues}"
