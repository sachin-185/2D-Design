"""The whole backend through HTTP, as the frontend uses it: P3's API -> P2's engine -> P1 solver -> P4 checker."""
import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from floorplan.api import app  # noqa: E402

CASES = Path(__file__).parent / "TestCases"
client = TestClient(app)


def load(name):
    return json.loads((CASES / f"{name}.json").read_text())["input"]


def room(layout, name):
    return next(r for r in layout["rooms"] if r["name"] == name)


@pytest.fixture(scope="module")
def t01():
    response = client.post("/generate", json=load("t01_standard"))
    assert response.status_code == 200, response.text
    return response.json()


def test_health_loads_every_part():
    body = client.get("/health").json()
    assert body["engine_loaded"] and body["solver_loaded"] and body["checker_loaded"]
    assert body["import_errors"] == {}


def test_generate_returns_three_checked_layouts_with_engine_extras(t01):
    assert len(t01["layouts"]) == 3
    for layout in t01["layouts"]:
        assert {"archetype", "penalties", "coverage_percent"} <= set(layout)
        assert any(d["between"][0] == "outside" for d in layout["doors"])


def test_too_small_plot_is_a_400_with_the_reason():
    response = client.post("/generate", json=load("t03_too_small"))
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["status"] == "infeasible" and "Plot too small" in detail["message"]


def test_bad_input_is_a_422():
    response = client.post("/generate", json={"plot": [30, 40], "rooms": [{"name": "x", "type": "garage"}]})
    assert response.status_code == 422


def test_edit_layout_keeps_locked_rooms_and_returns_the_next_input(t01):
    inp, layout = load("t01_standard"), t01["layouts"][0]
    wanted = 12 if room(layout, "bedroom")["w"] != 12 else 11
    response = client.post("/edit-layout", json={
        "input": inp, "layout": layout, "edits": {"bedroom": {"width": wanted}}, "lock": ["living"]})
    assert response.status_code == 200, response.text
    body = response.json()
    edited = body["layouts"][0]
    assert room(edited, "bedroom")["w"] == wanted
    assert {k: room(edited, "living")[k] for k in "xywh"} == {k: room(layout, "living")[k] for k in "xywh"}
    assert {"room": "living", "locked": True} in body["input"]["pins"]


def test_impossible_edit_gives_the_nearest_size(t01):
    response = client.post("/edit-layout", json={
        "input": load("t01_standard"), "layout": t01["layouts"][0], "edits": {"bedroom": {"width": 40}}})
    assert response.status_code == 400
    assert response.json()["detail"]["details"]["nearest"] == {"bedroom": {"width": 16}}


def test_render_returns_an_svg_with_every_room(t01):
    response = client.post("/render", json={"input": load("t01_standard"), "layout": t01["layouts"][0]})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    for r in t01["layouts"][0]["rooms"]:
        assert r["name"].upper() in response.text  # render.py writes labels in capitals
