"""H2 size limits for the secondary room types (aliases).

P3's final sizes: dining and study use the living room limits, and utility,
store, storage and laundry use the kitchen limits.
"""
import json
from pathlib import Path

import pytest

from floorplan.validator import BASE_SIZES, SIZE_ALIASES, SIZE_TABLE, check_size_limits
from validate_all import errors_only, validate_all

ROOT = Path(__file__).resolve().parent.parent

EXPECTED_BASE = {
    "dining": "living",
    "study": "living",
    "utility": "kitchen",
    "store": "kitchen",
    "storage": "kitchen",
    "laundry": "kitchen",
}


def h2_messages(room_type, w, h):
    inp = {"rooms": [{"name": "r", "type": room_type}]}
    layout = {"rooms": [{"name": "r", "x": 0, "y": 0, "w": w, "h": h}]}
    return [p["message"] for p in check_size_limits(inp, layout)]


def test_each_alias_uses_the_agreed_base_type():
    assert SIZE_ALIASES == EXPECTED_BASE


@pytest.mark.parametrize("alias, base", sorted(EXPECTED_BASE.items()))
def test_alias_has_the_same_limits_as_its_base(alias, base):
    assert SIZE_TABLE[alias] == SIZE_TABLE[base]


@pytest.mark.parametrize("alias", sorted(EXPECTED_BASE))
def test_alias_at_its_minimum_and_maximum_passes(alias):
    (min_w, min_h), (max_w, max_h) = SIZE_TABLE[alias]
    assert h2_messages(alias, min_w, min_h) == []
    assert h2_messages(alias, max_w, max_h) == []


@pytest.mark.parametrize("alias", sorted(EXPECTED_BASE))
def test_alias_just_outside_its_limits_fails(alias):
    (min_w, min_h), (max_w, max_h) = SIZE_TABLE[alias]
    assert any("below its minimum" in m for m in h2_messages(alias, min_w - 1, min_h))
    assert any("above its maximum" in m for m in h2_messages(alias, max_w + 1, max_h))


def test_alias_tables_are_copies_not_shared_lists():
    """Changing an alias entry by mistake must not change its base type too."""
    for alias, base in SIZE_ALIASES.items():
        assert SIZE_TABLE[alias][0] is not BASE_SIZES[base][0]
        assert SIZE_TABLE[alias][1] is not BASE_SIZES[base][1]


def test_t24_sizes_that_failed_before_now_pass():
    """Before this change dining 20 x 20 and utility 12 x 12 got H2 errors."""
    assert h2_messages("dining", 20, 20) == []
    assert h2_messages("utility", 12, 12) == []


def test_alias_keeps_its_own_type_for_connection_rules():
    """A dining room needs only to be reachable; it must not be treated as a second living room."""
    inp = {
        "plot": [24, 12], "entrance": "S", "north": "up",
        "rooms": [{"name": "living", "type": "living"}, {"name": "dining", "type": "dining"}],
    }
    layout = {
        "rooms": [
            {"name": "living", "x": 0, "y": 0, "w": 12, "h": 12},
            {"name": "dining", "x": 12, "y": 0, "w": 12, "h": 12},
        ],
        "hallway_segments": [],
    }
    assert errors_only(validate_all(inp, layout)) == []


def test_every_type_in_the_input_schema_has_a_size_rule():
    schema = json.loads((ROOT / "input_schema.json").read_text(encoding="utf-8"))
    types = schema["properties"]["rooms"]["items"]["properties"]["type"]["enum"]
    assert set(types) == set(SIZE_TABLE)
