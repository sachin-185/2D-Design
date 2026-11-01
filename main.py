
from floorplan.geometry import solve_layout
from validate_all import validate_solver_result


def report_occupied_area(result):
    rooms = result["rooms"]
    hallway_segments = result.get("hallway_segments", [])

    # Backward compatibility with the old single-hallway format
    if not hallway_segments and result.get("hallway"):
        hallway_segments = [result["hallway"]]

    occupied_area = 0

    print("\nOCCUPIED AREA BREAKDOWN:")

    for name, room in rooms.items():
        area = room["w"] * room["h"]
        occupied_area += area
        print(f"{name}: {area} sq ft")

    print("\nHALLWAY AREA BREAKDOWN:")

    for hallway in hallway_segments:
        area = hallway["w"] * hallway["h"]
        occupied_area += area
        print(f"{hallway['id']}: {area} sq ft")

    buildable_area = (
        result["buildable_width"] * result["buildable_depth"]
    )

    unused_area = buildable_area - occupied_area

    print(f"\nNumber of hallway segments: {len(hallway_segments)}")
    print(f"Buildable area: {buildable_area} sq ft")
    print(f"Occupied area: {occupied_area} sq ft")
    print(f"Unused area: {unused_area} sq ft")
    print(f"Coverage: {occupied_area / buildable_area * 100:.2f}%")

# 1. Define room dimensions
room_specs = {
    "living": {
        "min_width": 12,
        "max_width": 20,
        "min_height": 12,
        "max_height": 20
    },
    "bedroom_1": {
        "min_width": 10,
        "max_width": 16,
        "min_height": 10,
        "max_height": 16
    },
    "kitchen": {
        "min_width": 8,
        "max_width": 12,
        "min_height": 8,
        "max_height": 12
    },
    "bathroom": {
        "min_width": 5,
        "max_width": 8,
        "min_height": 7,
        "max_height": 10
    }
}


# 2. Define the input metadata
layout_input = {
    "plot": [30, 24],
    "setbacks": {
        "left": 0,
        "right": 0,
        "front": 0,
        "back": 0
    },
    "entrance": "S",
    "north": "up",
    "rooms": [
        {"name": "living", "type": "living"},
        {"name": "bedroom_1", "type": "bedroom"},
        {"name": "kitchen", "type": "kitchen"},
        {"name": "bathroom", "type": "bathroom"}
    ]
}


# 3. Generate the layout
result = solve_layout(
    plot_width=30,
    plot_height=24,
    room_specs=room_specs,
    layout_input=layout_input,
    include_hallway=True,
    require_full_coverage=False,
    max_hallway_segments=6,
    time_limit_seconds=60
)

if result["status"] == "success":
    report_occupied_area(result)

# 4. Display and validate the result
print("\nSOLVER RESULT:")
print(result)

if result["status"] == "success":
    problems = validate_solver_result(layout_input, result)

    print("\nVALIDATION RESULT:")

    if not problems:
        print("All P4 validation checks passed!")
    else:
        for problem in problems:
            print(problem)
else:
    print("\nSolver did not generate a feasible layout.")
    print(result["message"])
