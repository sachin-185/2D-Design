"""
Run a wrapped JSON floor-plan test case through the whole engine.

Expected JSON structure:
{
    "name": "...",
    "input": {...},
    "expect": {"status": "..."}
}

    python -m floorplan.json_runner tests/TestCases/t01_standard.json
"""

import argparse
import json
from pathlib import Path
from pprint import pprint

from floorplan.engine import solve_request


def run_json_file(json_path):
    json_path = Path(json_path)

    print("\n" + "=" * 60)
    print(f"RUNNING TEST CASE: {json_path.name}")
    print("=" * 60)

    # 1. Load the complete JSON document
    with json_path.open("r", encoding="utf-8") as file:
        test_case = json.load(file)

    case_name = test_case.get("name", json_path.stem)
    input_data = test_case["input"]
    expected_status = test_case.get("expect", {}).get("status")

    print("Test case:", case_name)
    print("Expected status:", expected_status)

    # 2. Run the engine. Only layouts P4 accepted come back.
    result = solve_request(input_data)
    final_status = result["status"]

    print("\nFinal status:", final_status)

    if expected_status:
        print(
            "Expectation match:",
            "YES" if final_status == expected_status else "NO"
        )

    for message in result["messages"]:
        print("Message:", message)

    for index, layout in enumerate(result["layouts"], start=1):
        print(
            f"\nLayout {index}: {layout['archetype'] or 'free plan'}, "
            f"score {layout['score']}, {layout['coverage_percent']}% coverage"
        )
        pprint(layout)

    return {
        "case": case_name,
        "expected_status": expected_status,
        "final_status": final_status,
        "expectation_match": (
            final_status == expected_status
            if expected_status else None
        ),
        "layouts": result["layouts"],
        "messages": result["messages"],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run a JSON test case through the whole engine."
    )

    parser.add_argument(
        "json_file",
        help="Path to the JSON test case."
    )

    args = parser.parse_args()
    run_json_file(args.json_file)


if __name__ == "__main__":
    main()
