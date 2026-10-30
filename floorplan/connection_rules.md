# Connection rules (draft v1, for team review)

Owner: P4. These rules are shared by the solver (P1, P2) and the validator (P4), so both must agree on them. Change them only after the whole team agrees.

## Definitions

- All rooms are rectangles. Lengths are whole feet on a 1 ft grid.
- Coordinates: x grows east, y grows north, origin (0, 0) is the bottom-left corner of the buildable area (the plot minus setbacks).
- Two rooms are connected if they share a wall segment of at least DOOR_MIN = 3 ft.
- Rooms that only touch at a corner are not connected.
- Doors sit at least 1 ft from a room corner, so a door needs a shared wall of at least DOOR_MIN + 2 ft = 5 ft to have a valid position on both sides. (Team to confirm: if not, a 3 ft shared wall is enough and the door may be centered.)
- The MVP has **one hallway segment**: one straight rectangle with the id **hallway_1** (agreed with P1). It may be given in the layout as "hallway" (one rectangle) or as a list "hallway_segments", so L and T shapes can be added later without changing the format. Width 3 to 4 ft (short side) and length at least 12 ft (long side) are placeholder numbers to be confirmed. The engine adds the hallway; the user does not list it.
- Shared wall length for rooms A and B:
  - A directly west of B (A.x + A.w == B.x): min(A.y + A.h, B.y + B.h) - max(A.y, B.y)
  - A directly south of B (A.y + A.h == B.y): min(A.x + A.w, B.x + B.w) - max(A.x, B.x)
  - The other two directions are the same with A and B swapped.

## Required connections

| Room | Must share a door-sized wall with |
| --- | --- |
| Living room | The entrance side wall, and the hallway or dining |
| Kitchen | Living or dining |
| Each bedroom | The hallway |
| Bathroom | The hallway, or its attached bedroom |
| Hallway | The living room, so you can walk in from the entrance |

## Entrance wall

- The entrance is only a **side** of the plot (N, E, S or W) in the MVP. The exact position of the main door along that side is not modelled.
- The living room is the entrance room. It must touch the boundary of the buildable area on the entrance side.
- The real-world side is turned into an edge of the drawing using the `north` field. With north up, entrance S means the bottom edge. With north pointing left, entrance N means the left edge.
- Coordinates (shared by P1 and P4): feet, origin at the bottom-left corner of the buildable area (the plot minus setbacks), so "touching the boundary" means touching the edge of the buildable area.

## Reachability

- Every room must be reachable from the entrance room by walking through connected rooms.
- The entrance room is the living room, on the entrance side.

## Forbidden patterns

| Code | Pattern |
| --- | --- |
| F1 | A bedroom reachable only through another bedroom |
| F2 | A door between bathroom and kitchen |
| F3 | A toilet door facing the main entrance (suggested definition: a bathroom door must not be on the entrance wall and must not open directly into the entrance room) |
| F4 | A bedroom with no door |
| F5 | Any room that cannot be reached from the entrance |

## Problem codes the checker reports

| Code | Meaning |
| --- | --- |
| H1 | A room sticks out of the buildable area |
| H2 | A room is outside its size limits, a pinned size was not held, or the room type has no size rule |
| H3 | Two rooms overlap |
| H4 | Rooms and hallway do not fill the buildable area exactly |
| H6 | A pair of rooms that must connect do not share a wall of at least 3 ft |
| HW1 | The hallway is the wrong width or too short |
| E1 | The living room does not touch the entrance wall |
| F1 | A bedroom can only be reached through another bedroom |
| F5 | A room cannot be reached from the entrance room |
| F2, F3, F4 | Door based patterns (not built yet, they need door positions from P5) |

## Status words used in test files and engine results

- valid: a layout was produced and passed every check
- infeasible: the input cannot be satisfied (for example, plot too small), with a message saying by how much
- conflict: the user's preferences contradict each other, with a message naming the rooms

## Open decisions for the team

1. Test t07 (plot too large for the rooms): suggested result is infeasible, with a message that the rooms cannot fill the plot.
2. Test t08 (two rooms forced into the same zone): suggested result is conflict, naming both rooms.
3. Is a 3 ft shared wall enough, or do we require 5 ft so a door can sit 1 ft from each corner?
4. Definition of F3.
5. Bathroom attached to a bedroom: does it connect to that bedroom instead of the hallway? Proposed: an optional `attached_to` field on the bathroom (P3 to confirm). Today the checker requires every bathroom to touch the hallway.
6. Hallway width and length numbers (3 to 4 ft wide, at least 12 ft long are placeholders). To be confirmed with P2 or the team.
7. Several hallway segments (L and T shapes): deferred. If added, segments share a boundary of at least the hallway width, have the same width, and a disconnected segment is reported.
