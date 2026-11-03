# Connection rules (draft v2, for team review)

Owner: P4. These rules are shared by the solver (P1, P2) and the validator (P4), so both must agree on them. Change them only after the whole team agrees.

What changed from v1: the hallway can now have several segments (HW2, HW3, corridor length rule), rooms connect to "any hallway segment", problems have a severity (error or warning), and less than full coverage is a warning. The required connections table now matches the code.

## Definitions

- All rooms are rectangles. Lengths are whole feet on a 1 ft grid.
- Coordinates: x grows east (right), y grows north (up), origin (0, 0) is the bottom-left corner of the buildable area (the plot minus setbacks). The solver keeps the input orientation in its output (it rotates back if it rotates internally).
- Two rooms are connected if they share a wall segment of at least DOOR_MIN = 3 ft.
- Rooms that only touch at a corner are not connected.
- Doors sit at least 1 ft from a room corner, so a door needs a shared wall of at least DOOR_MIN + 2 ft = 5 ft to have a valid position on both sides. (Open decision 3: today the code uses 3 ft.)
- Shared wall length for rooms A and B:
  - A directly west of B (A.x + A.w == B.x): min(A.y + A.h, B.y + B.h) - max(A.y, B.y)
  - A directly south of B (A.y + A.h == B.y): min(A.x + A.w, B.x + B.w) - max(A.x, B.x)
  - The other two directions are the same with A and B swapped.

## Hallway

- The hallway is one continuous corridor made of one or more rectangular segments. The solver decides how many (at most 6 candidate slots in the current solver). The user does not list the hallway.
- Layout format: a list `hallway_segments`, each with `id`, `x`, `y`, `w`, `h`. Segments are named `hallway_1`, `hallway_2`, and so on. A single rectangle given as `hallway` is still accepted.
- Width: the short side of every segment is 3 to 4 ft (placeholder numbers, open decision 6).
- Length: the sum of the long sides of all segments is at least 12 ft. The 12 ft applies to the whole corridor, not to each segment.
- Segments are connected when they share a wall of at least 3 ft (the same shared wall formula as rooms). A corner touch does not count. All segments must form one connected group using only these links, never by passing through a room (HW2). With one segment this rule does not apply.
- No 5 x 5 ft square may fit inside the hallway segments taken together (HW3). This stops two segments from being stacked into a wide block. A 4 ft wide corridor, an L shape and a T shape pass.
- Segments must not overlap rooms or each other, and they count as floor area in the coverage rule.

## Required connections

| Room | Must share a wall of at least 3 ft with |
| --- | --- |
| Living room | The entrance side wall of the buildable area, and any hallway segment only if the layout has at least one hallway segment |
| Kitchen | The first living room |
| Each bedroom | Any hallway segment OR any living room (either one is enough) |
| Each bathroom | Any hallway segment OR any living room (either one is enough; the attached-bedroom option is not decided, open decision 5) |
| Dining, utility, store | Nothing is required directly. They only need to be reachable (see Reachability) |

A layout may have no hallway at all (team decision, for small plots). Then the living room has no hallway requirement, bedrooms and bathrooms must touch a living room, and HW1, HW2 and HW3 do not apply. A bedroom touching only the kitchen, or nothing, is still an H6 error.

In code, the solver side (`required_pairs`) returns `(room, "hallway")` where `"hallway"` means any segment. The checker side (`expected_connections`) is written separately and a test confirms the two agree. Both still list the strict hallway pairs. The checker applies the living room alternative and the optional hallway inside `check_required_connections`. The solver side still uses the strict hallway rule until P1 updates it.

## Entrance wall

- The entrance is only a **side** of the plot (N, E, S or W) in the MVP. The exact position of the main door along that side is not modelled.
- The living room is the entrance room. It must touch the boundary of the buildable area on the entrance side (E1).
- The real-world side is turned into an edge of the drawing using the `north` field. With north up, entrance S means the bottom edge. With north pointing left, entrance N means the left edge.

## Reachability

- Rooms and hallway segments are the nodes. A shared wall of at least 3 ft is a link.
- Every room must be reachable from the entrance room (the first living room) by walking through linked nodes (F5).
- Bedrooms are dead ends. You can walk into a bedroom but not through it to reach another room (F1). All other rooms and the hallway can be walked through.

## Coverage

- Rooms plus hallway should fill the buildable area. The solver tries full coverage first. If that is impossible it may return the best layout with unused area.
- Unused area is a **warning** (H4). It never breaks a hard rule just to reduce unused area.
- Extra area (rooms and hallway add up to more than the buildable area, which means a room sticks out or two overlap) is an **error** (H4, together with H1 and H3).
- Planned, not built yet: usable leftover space must be reachable. Any unused piece that fits a 3 x 3 ft square must share at least 3 ft of wall with a hallway segment. Smaller pieces are ignored. A closed-off pocket is not allowed.

## Forbidden patterns

| Code | Pattern |
| --- | --- |
| F1 | A bedroom reachable only through another bedroom |
| F2 | A door between bathroom and kitchen |
| F3 | A toilet door facing the main entrance (suggested definition: a bathroom door must not be on the entrance wall and must not open directly into the entrance room) |
| F4 | A bedroom with no door |
| F5 | Any room that cannot be reached from the entrance |

## Problem codes the checker reports

A problem is `{code, message, rooms, severity}`. Severity is `error` (the layout is invalid) or `warning` (reported only). A problem without a severity counts as an error. A layout is valid when it has no errors (`is_valid` in validate_all.py).

| Code | Severity | Meaning |
| --- | --- | --- |
| H1 | error | A room or hallway segment sticks out of the buildable area |
| H2 | error | A room is outside its size limits, a pinned size was not held, or the room type has no size rule |
| H3 | error | Two rooms overlap |
| H4 | warning or error | Rooms and hallway do not fill the buildable area. Unused area is a warning, extra area is an error |
| H6 | error | A required connection is missing: less than 3 ft of shared wall. A bedroom or bathroom touches neither a hallway segment nor a living room, a living room does not touch the hallway when there is one, or a kitchen does not touch the first living room |
| HW1 | error | A hallway segment is not 3 to 4 ft wide, or the total corridor length is under 12 ft |
| HW2 | error | Hallway segments are not one connected group |
| HW3 | error | A 5 x 5 ft square fits inside the hallway segments |
| E1 | error | The living room does not touch the entrance wall |
| F1 | error | A bedroom can only be reached through another bedroom |
| F5 | error | A room cannot be reached from the entrance room |
| F2, F3, F4 | error | Door based patterns (not built yet, they need door positions from P5) |

## Status words used in test files and engine results

- valid: a layout was produced and has no errors (warnings are allowed)
- infeasible: the input cannot be satisfied (for example, plot too small), with a message saying by how much
- conflict: the user's preferences contradict each other, with a message naming the rooms

## Open decisions for the team

1. Test t07 (plot too large for the rooms): suggested result is infeasible, with a message that the rooms cannot fill the plot. This now needs review, because partial coverage is allowed.
2. Test t08 (two rooms forced into the same zone): suggested result is conflict, naming both rooms.
3. Is a 3 ft shared wall enough, or do we require 5 ft so a door can sit 1 ft from each corner?
4. Definition of F3.
5. Bathroom attached to a bedroom: does it connect to that bedroom instead of the hallway? Proposed: an optional `attached_to` field on the bathroom (P3 to confirm). Today every bathroom must touch a hallway segment.
6. Hallway numbers (3 to 4 ft wide, total length at least 12 ft) are placeholders. To be confirmed with P2 or the team.
7. Maximum share of unused area (for example warn above one number, error above another). Not decided.
8. Whether bedrooms and bathrooms may be reached through the living room instead of the hallway. Decided by the team: yes. A bedroom or bathroom may touch any hallway segment or any living room, and a layout may have no hallway. Built in the checker; the solver side (P1) will follow later.
9. Rule code list: the codes above are placeholders until the team agrees one list.
10. Who retries the solver when the checker finds errors.