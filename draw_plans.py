"""Run the engine on every test input and draw each layout as a floor plan.

    python draw_plans.py                 # all files in tests/TestCases
    python draw_plans.py t01 t11         # only names starting with these

Writes output/plans.html (the 3 layouts per input) and prints a short summary. A demo drawing until
P5's render.py and Streamlit page land.
"""
import html
import json
import sys
from pathlib import Path

from floorplan.engine import OUTSIDE, entrance_wall, shared_wall, solve_request
from floorplan.geometry import ENTRANCE_EDGE, calculate_buildable_area
from floorplan.preferences import DOOR_MIN

ROOT = Path(__file__).parent
CASES = ROOT / "tests" / "TestCases"
OUT = ROOT / "output" / "plans.html"

FT = 12  # pixels per foot
FILL = {
    "living": "#f6d7a7", "dining": "#e8d5f2", "kitchen": "#f4b6a6", "bedroom": "#b9d7ea",
    "bathroom": "#c8e6c9", "utility": "#ece6d5", "store": "#ece6d5", "hallway": "#e6e6e6",
}
WALL = "#333"
DOOR = "#c0392b"
ENTRY = "#2e7d32"


def door_on(wall):
    """A DOOR_MIN wide opening in the middle of a wall."""
    (x1, y1), (x2, y2) = wall
    if x1 == x2:
        mid = (y1 + y2) / 2
        return (x1, mid - DOOR_MIN / 2), (x1, mid + DOOR_MIN / 2)
    mid = (x1 + x2) / 2
    return (mid - DOOR_MIN / 2, y1), (mid + DOOR_MIN / 2, y1)


def draw(inp, layout):
    """SVG of the plot, setbacks, rooms, hallway, doors, entrance and a north arrow."""
    plot_w, plot_l = inp["plot"]
    setbacks = {"left": 0, "right": 0, "front": 0, "back": 0, **inp.get("setbacks", {})}
    area = calculate_buildable_area(plot_w, plot_l, setbacks)
    bw, bd, ox, oy = area["width"], area["depth"], area["offset_x"], area["offset_y"]
    pad = 40
    W, H = plot_w * FT + 2 * pad, plot_l * FT + 2 * pad

    def px(x):  # buildable feet -> svg pixels
        return pad + (ox + x) * FT

    def py(y):  # y grows north in the plan, down in SVG
        return pad + (plot_l - oy - y) * FT

    def line(seg, color, width):
        (x1, y1), (x2, y2) = seg
        return (f'<line x1="{px(x1)}" y1="{py(y1)}" x2="{px(x2)}" y2="{py(y2)}" '
                f'stroke="{color}" stroke-width="{width}"/>')

    out = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
           f'font-family="system-ui, sans-serif">',
           '<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" '
           'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="#bbb" stroke-width="2"/>'
           '</pattern><marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" '
           'markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#333"/></marker></defs>',
           f'<rect x="{pad}" y="{pad}" width="{plot_w * FT}" height="{plot_l * FT}" fill="#fafafa" '
           f'stroke="#999" stroke-dasharray="6 4"/>',
           f'<rect x="{px(0)}" y="{py(bd)}" width="{bw * FT}" height="{bd * FT}" fill="#fff" stroke="#999"/>']

    types = {r["name"]: r["type"] for r in inp["rooms"]}
    boxes = list(layout["rooms"]) + [{**h, "name": h["id"]} for h in layout["hallway_segments"]]
    for r in boxes:
        kind = types.get(r["name"], "hallway")
        fill = "url(#hatch)" if kind == "hallway" else FILL.get(kind, "#eee")
        out.append(f'<rect x="{px(r["x"])}" y="{py(r["y"] + r["h"])}" width="{r["w"] * FT}" '
                   f'height="{r["h"] * FT}" fill="{fill}" stroke="{WALL}" stroke-width="3"/>')
        cx, cy = px(r["x"] + r["w"] / 2), py(r["y"] + r["h"] / 2)
        label = "hallway" if kind == "hallway" else r["name"]
        size = 10 if min(r["w"], r["h"]) < 5 else 12
        rotate = f' transform="rotate(-90 {cx} {cy})"' if r["h"] > r["w"] and r["w"] < 6 else ""
        out.append(f'<text x="{cx}" y="{cy - 2}" text-anchor="middle" font-size="{size}" font-weight="600"'
                   f'{rotate}>{html.escape(label)}</text>')
        out.append(f'<text x="{cx}" y="{cy + size}" text-anchor="middle" font-size="{size - 1}" fill="#555"'
                   f'{rotate}>{r["w"]}×{r["h"]} ft</text>')

    # doors from the engine: a white gap with the door drawn in it
    by_name = {b["name"]: b for b in boxes}
    edge = ENTRANCE_EDGE[inp.get("north", "up")][inp.get("entrance", "S")]
    for door in layout["doors"]:
        a, b = door["between"]
        if a == OUTSIDE:
            seg = door_on(entrance_wall(inp, by_name[b], bw, bd))
            out.append(line(seg, "#fff", 7))
            out.append(line(seg, ENTRY, 5))
            (x1, y1), (x2, y2) = seg
            mx, my = px((x1 + x2) / 2), py((y1 + y2) / 2)
            off = {"bottom": (0, 26), "top": (0, -18), "left": (-30, 4), "right": (30, 4)}[edge]
            out.append(f'<text x="{mx + off[0]}" y="{my + off[1]}" text-anchor="middle" font-size="11" '
                       f'fill="{ENTRY}" font-weight="600">ENTRY</text>')
        else:
            seg = door_on(shared_wall(by_name[a], by_name[b]))
            out.append(line(seg, "#fff", 5))
            out.append(line(seg, DOOR, 2))

    # north arrow, top right
    ax, ay = W - 26, 26
    dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[inp.get("north", "up")]
    out.append(f'<line x1="{ax - dx * 12}" y1="{ay - dy * 12}" x2="{ax + dx * 12}" y2="{ay + dy * 12}" '
               f'stroke="#333" stroke-width="2" marker-end="url(#arrow)"/>')
    out.append(f'<text x="{ax + dx * 22}" y="{ay + dy * 22 + 4}" text-anchor="middle" font-size="11" '
               f'font-weight="700">N</text>')
    out.append("</svg>")
    return "\n".join(out)


def solve_case(path):
    data = json.load(open(path))
    result = solve_request(data["input"])
    return {"name": data.get("name", path.stem), "inp": data["input"],
            "expect": data.get("expect", {}).get("status"), "res": result}


def card(case):
    inp, res = case["inp"], case["res"]
    w, l = inp["plot"]
    facts = f'Plot {w}×{l} ft · entrance {inp.get("entrance", "S")} · north {inp.get("north", "up")}'
    status = res["status"]
    body = "".join(f'<p class="bad">{html.escape(m)}</p>' for m in res["messages"])
    for index, layout in enumerate(res["layouts"], start=1):
        shape = (layout["archetype"] or "free plan").replace("_", " ")
        rows = "".join(
            f'<tr><td>{html.escape(r["name"])}</td><td>{r["w"]}×{r["h"]}</td><td>{r["w"] * r["h"]}</td></tr>'
            for r in layout["rooms"] + [{**h, "name": h["id"]} for h in layout["hallway_segments"]])
        notes = "".join(f'<p class="muted">{html.escape(m)}</p>' for m in layout["messages"])
        body += (f'<h3>Layout {index}: {html.escape(shape)}</h3>'
                 f'<p class="ok">Checks pass · {layout["coverage_percent"]}% of the plot used · '
                 f'penalty score {layout["score"]}</p>'
                 f'<div class="plan">{draw(inp, layout)}</div>{notes}'
                 f'<table><tr><th>Room</th><th>Size (ft)</th><th>Area (sq ft)</th></tr>{rows}</table>')
    match = "" if case["expect"] in (None, "pending") else (
        " ✓" if case["expect"] == status else f' ✗ expected {case["expect"]}')
    return (f'<section><h2>{html.escape(case["name"])} <span class="tag {status}">{status}{match}</span></h2>'
            f'<p class="muted">{facts}</p>{body}</section>')


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Floor Plan Results</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font-family:system-ui,sans-serif;margin:0;padding:24px 16px;background:#f2f2f0;color:#222}}
h1{{margin:0 0 4px}} .muted{{color:#666;font-size:14px;margin:4px 0}}
main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,480px),1fr));gap:16px;margin-top:16px}}
section{{background:#fff;border-radius:10px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
h2{{font-size:17px;margin:0}} h3{{font-size:15px;margin:16px 0 2px}} .plan svg{{max-width:100%;height:auto}}
.tag{{font-size:12px;padding:2px 8px;border-radius:10px;margin-left:6px;vertical-align:middle}}
.valid{{background:#d7f0dc;color:#1e6b31}} .infeasible,.conflict,.invalid,.timeout{{background:#f6d6d2;color:#8a2a1d}}
.ok{{color:#1e6b31;font-weight:600;font-size:14px;margin:2px 0}} .bad{{color:#8a2a1d;font-weight:600}}
table{{border-collapse:collapse;font-size:13px;margin-top:6px}} td,th{{padding:3px 10px;border-bottom:1px solid #eee;text-align:left}}
.legend span{{display:inline-block;margin-right:12px;font-size:13px}}
.legend i{{display:inline-block;width:12px;height:12px;margin-right:4px;vertical-align:-1px;border:1px solid #888}}
</style></head><body>
<h1>Floor plan results</h1>
<p class="muted">Each input runs through the engine: P1 geometry, P2 preferences, then P4's independent checker. Dashed line = plot, solid = buildable area.</p>
<p class="legend">{legend}<span><i style="background:{entry}"></i>main door</span><span><i style="background:{door}"></i>interior door (3 ft)</span></p>
<main>{cards}</main></body></html>"""


def main(prefixes):
    paths = sorted(p for p in CASES.glob("*.json") if not prefixes or p.stem.startswith(tuple(prefixes)))
    cases = []
    for path in paths:
        case = solve_case(path)
        cases.append(case)
        res = case["res"]
        shapes = ", ".join(f'{l["archetype"] or "free"} {l["coverage_percent"]}%' for l in res["layouts"])
        print(f'{case["name"]:24} expect {str(case["expect"]):11} -> {res["status"]:10} {shapes}')
    legend = "".join(f'<span><i style="background:{c}"></i>{k}</span>' for k, c in FILL.items())
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(PAGE.format(legend=legend, door=DOOR, entry=ENTRY, cards="".join(card(c) for c in cases)),
                   encoding="utf-8")
    print(f"\nDrawings written to {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
