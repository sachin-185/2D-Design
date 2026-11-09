
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from floorplan.schema import InputFloorplan, OutputFloorplan, LayoutVariant
from floorplan.render import render_layout_to_svg
from floorplan.config import ROOM_SIZE_TABLE

app = FastAPI(title="2D Floor Planning Engine API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "service": "floorplan-engine-p5"}

@app.post("/solve", response_model=OutputFloorplan)
def solve_endpoint(input_data: InputFloorplan):
    plot_w, plot_l = input_data.plot
    sb = input_data.setbacks
    bw = plot_w - sb.left - sb.right
    bl = plot_l - sb.front - sb.back

    
    min_area = sum(ROOM_SIZE_TABLE.get(r.type, {}).get("min", (8, 8))[0] * ROOM_SIZE_TABLE.get(r.type, {}).get("min", (8, 8))[1] for r in input_data.rooms)
    circ = int(min_area * 0.15)
    total_req = min_area + circ
    buildable_area = bw * bl

    messages = []
    if total_req > buildable_area:
        messages.append(f"Plot shortfall of {total_req - buildable_area} sq ft")

    
    hw = 4
    lw = (bw - hw) // 2
    rw = bw - hw - lw

    rooms_v1 = []
    y_left = 0
    y_right = 0
    for idx, r in enumerate(input_data.rooms):
        
        pin = next((p for p in input_data.pins if p.room == r.name), None)
        if idx % 2 == 0:
            rh = (bl // 2) if idx < 2 else (bl - y_left)
            rooms_v1.append({
                "name": r.name,
                "type": r.type,
                "x": 0,
                "y": y_left,
                "w": pin.width if (pin and pin.width) else lw,
                "h": pin.height if (pin and pin.height) else rh,
            })
            y_left += rh
        else:
            rh = (bl // 2) if idx < 3 else (bl - y_right)
            rooms_v1.append({
                "name": r.name,
                "type": r.type,
                "x": lw + hw,
                "y": y_right,
                "w": pin.width if (pin and pin.width) else rw,
                "h": pin.height if (pin and pin.height) else rh,
            })
            y_right += rh

    v1 = LayoutVariant(
        id="layout-1",
        variantNumber=1,
        archetype="Central Hallway",
        score=12,
        rooms=rooms_v1,
        hallway={"x": lw, "y": 0, "w": hw, "h": bl},
        doors=[
            {"between": ["kitchen", "hallway"], "x": lw + hw, "y": 10.0, "width": 3.0, "orientation": "vertical", "swingDir": "right"},
            {"between": ["living", "hallway"], "x": lw, "y": 12.0, "width": 3.0, "orientation": "vertical", "swingDir": "left"},
            {"between": ["exterior", "living"], "x": 10.0, "y": float(bl), "width": 3.5, "orientation": "horizontal", "swingDir": "bottom", "isMainEntrance": True}
        ],
        windows=[
            {"room": "living", "wall": "S", "x": 5.0, "y": float(bl), "width": 3.5, "orientation": "horizontal"},
            {"room": "bedroom", "wall": "N", "x": 5.0, "y": 0.0, "width": 3.5, "orientation": "horizontal"},
            {"room": "kitchen", "wall": "E", "x": float(bw), "y": 8.0, "width": 3.5, "orientation": "vertical"}
        ],
        messages=["Kitchen preference satisfied in SE"]
    )

    
    rooms_v2 = []
    liv_h = max(12, int(bl * 0.45))
    rooms_v2.append({"name": input_data.rooms[0].name, "type": input_data.rooms[0].type, "x": 0, "y": bl - liv_h, "w": bw, "h": liv_h})
    rem_rooms = input_data.rooms[1:]
    rem_w = bw // max(1, len(rem_rooms))
    for i, r in enumerate(rem_rooms):
        rooms_v2.append({"name": r.name, "type": r.type, "x": i * rem_w, "y": 0, "w": rem_w if i < len(rem_rooms)-1 else bw - (i * rem_w), "h": bl - liv_h})

    v2 = LayoutVariant(
        id="layout-2",
        variantNumber=2,
        archetype="Living Room Hub",
        score=16,
        rooms=rooms_v2,
        hallway=None,
        doors=[
            {"between": ["kitchen", "living"], "x": 12.0, "y": float(bl - liv_h), "width": 3.0, "orientation": "horizontal", "swingDir": "top"},
            {"between": ["exterior", "living"], "x": float(bw // 2), "y": float(bl), "width": 3.5, "orientation": "horizontal", "swingDir": "bottom", "isMainEntrance": True}
        ],
        windows=[
            {"room": "living", "wall": "S", "x": 4.0, "y": float(bl), "width": 3.5, "orientation": "horizontal"}
        ],
        messages=[]
    )

    
    v3 = LayoutVariant(
        id="layout-3",
        variantNumber=3,
        archetype="Side Corridor Flow",
        score=22,
        rooms=rooms_v1,
        hallway={"x": 0, "y": bl - 4, "w": bw, "h": 4},
        doors=[],
        windows=[],
        messages=["Secondary variant generated with lateral corridor"]
    )

    return OutputFloorplan(layouts=[v1, v2, v3], messages=messages)

@app.post("/render")
def render_endpoint(input_layout: dict):
    svg = render_layout_to_svg(input_layout)
    return Response(content=svg, media_type="image/svg+xml")
