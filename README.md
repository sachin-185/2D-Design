# PlanCraft 2D - Floor Planning Engine (P5 Role & Team Integration)

A modern, high-precision architectural floor planning front end and SVG vector rendering engine built with React, Vite, and standard SVG. Fully aligned with the team's pipeline contracts (P1, P2, P3, P4, P5).

---

## 🎯 P5 Integration Updates

1. **Layout & Hallway**:
   - `rooms`: `{ name, x, y, w, h, type }`.
   - `hallway_segments`: List of `{ id, x, y, w, h }` (can be empty `[]` or omitted when no hallway is present).
2. **Coordinates**:
   - **Whole feet from the BOTTOM-LEFT of the buildable area (0,0)**.
   - SVG canvas properly inverts $Y$ coordinates ($\text{svg\_y} = bY + (L_{build} - (y + h)) \times \text{scale}$) so plans draw right-side-up.
3. **Room Types (10 P3 Allowed Types)**:
   - `living`, `kitchen`, `bedroom`, `bathroom`, `dining`, `study`, `utility`, `store`, `storage`, `laundry`.
   - Up to 10 rooms allowed. ("office" has been replaced by "study").
4. **API Endpoints**:
   - Uses `POST /generate` for new layout requests and `POST /edit` for pinned re-solves.
   - Supports single layout responses from P3.
5. **Failures & Errors**:
   - Infeasible inputs halt immediately and display the exact shortfall in sq ft without generating fake plans.
   - API / backend errors are displayed with full server diagnostic messages.
6. **Real Checker Integration**:
   - Checker problems format: `{ code, message, rooms, severity }` (`severity`: `'error'` | `'warning'`).
   - Active checker matrix: `I1`, `H1`, `H2`, `H3`, `H4` (advisory warning), `H6`, `HW1`, `HW2`, `HW3`, `E1`, `F1`, `F2`, `F3`, `F4`, `F5`.
7. **Door Placement Logic**:
   - Bedroom and common bathroom connect to any hallway segment or living room.
   - Attached bathroom (`attached_to`) connects directly to its named bedroom.
   - Kitchen connects to the first living room (or circulation).
   - Unconnected rooms are tracked and surfaced as errors.
   - Python backend implementation provided in `floorplan/doors.py`.
8. **Edit Panel Fix**:
   - Double-solve race condition resolved: single atomic re-solve with pinned values.

---

## 💬 Team Q&A Answers (P5 to P3/P4)

### A. Can door placement move to the Python backend?
**Yes!** We created `floorplan/doors.py` with `place_doors(...)`. P3's runner and P4's validator can import it directly:
```python
from floorplan.doors import place_doors

doors, unconnected = place_doors(
    rooms=layout["rooms"],
    hallway_segments=layout.get("hallway_segments"),
    entrance=input_data.get("entrance", "S"),
    buildable_bounds=(buildable_w, buildable_l),
    room_requests=input_data.get("rooms", [])
)
```
The React front end renders doors returned in `layout.doors` by the backend.

### B. What is your final door format?
```json
{
  "between": ["bedroom 1", "hallway_1"],
  "x": 12.0,
  "y": 14.0,
  "width": 3.0,
  "orientation": "horizontal",
  "swingDir": "in",
  "isMainEntrance": false
}
```
* **$x$ and $y$**: The start coordinate (lower $x$ if horizontal, or lower $y$ if vertical) of the 3 ft door opening in feet from the **bottom-left of the buildable area**.
* **Fractions**: Whole feet are standard on the 1 ft grid; half-feet (`.5`) are supported when centering a door on an even-length wall.
* **`orientation`**: `"horizontal"` (runs along an East-West wall) or `"vertical"` (runs along a North-South wall).
* **`swingDir`**: `"in"`, `"out"`, `"left"`, or `"right"` into the connected room.

### C. Door between hallway segments: can "between" use the real segment id, such as `hallway_1`?
**Yes!** `"between"` supports any room name or hallway segment id (e.g. `["bedroom 1", "hallway_1"]` or `["hallway_1", "hallway_2"]`).

### D. Your 1 ft corner gap needs a 5 ft wall, but we connect at 3 ft. Is the gap a must?
**No, the 1 ft corner gap is NOT a must.** It is a soft architectural preference. On walls with length $3 \le \text{length} < 5$ ft, the 3 ft door connects with a $0$ ft corner gap. When a wall is $\ge 5$ ft, a 1 ft setback is applied for architrave clearance.

---

## 🏗️ Project Architecture & Folder Layout

```
2D Design/
├── frontend/                     # React + Vite Frontend (P5 UI & Canvas)
│   ├── src/
│   │   ├── components/           # Canvas, InputForm, EditPanel, Header, etc.
│   │   ├── engine/               # Client-side solver, contracts, checker, doors & windows
│   │   ├── App.jsx               # Main application container
│   │   ├── main.jsx              # React entry point
│   │   └── index.css             # Architectural blueprint styling
│   ├── index.html                # Vite HTML template
│   ├── vite.config.js            # Vite configuration with proxy to port 8000
│   └── package.json              # Frontend dependencies (React, Vite, Lucide)
├── backend/                      # Python FastAPI Engine & Door Logic (P3/P4)
│   ├── floorplan/
│   │   ├── api.py                # FastAPI REST API endpoints (/solve, /render)
│   │   ├── config.py             # Room size table & default setbacks
│   │   ├── doors.py              # Door placement algorithm
│   │   ├── render.py             # Server-side SVG rendering
│   │   └── schema.py             # Pydantic input/output schemas
│   └── requirements.txt          # Python dependencies (fastapi, uvicorn, ortools)
├── tests/
│   └── test_p5_pipeline.js       # Pipeline & contract validation test suite
├── package.json                  # Root monorepo orchestrator (npm run dev, test, build)
└── README.md                     # Documentation
```

---

## 🚀 Running the Project

From the project root (`PS C:\Users\sachi\Downloads\2D Design>`):

### Option 1: Frontend Only (Instant Client-side Engine)
```bash
npm run dev
```
*Accessible at `http://localhost:3000`.*

### Option 2: Full Stack (Frontend + Python Backend)
* **Start Python Backend**:
  ```bash
  npm run backend:dev
  # or: python -m uvicorn floorplan.api:app --app-dir backend --reload --port 8000
  ```
* **Start React Frontend**:
  ```bash
  npm run dev
  ```

### Option 3: Run Validation Tests
```bash
npm test
```
