
"""
Run a wrapped JSON floor-plan test case through P1 and P4.

Expected JSON structure:
{
    "name": "...",
    "input": {...},
    "expect": {"status": "..."}
}

Room-size configuration is temporary until P3 confirms
the authoritative configuration.
"""

import argparse
import json
from pathlib import Path
from pprint import pprint

from floorplan.geometry import solve_layout
from floorplan.input_adapter import build_solver_arguments
from validate_all import validate_solver_result


# TEMPORARY TEST CONFIGURATION ONLY
TEST_ROOM_SIZE_TABLE = {
    "living": ([12, 12], [20, 20]),
    "dining": ([10, 10], [16, 16]),
    "kitchen": ([8, 8], [12, 12]),
    "bedroom": ([10, 10], [16, 16]),
    "bathroom": ([5, 7], [8, 10]),
    "utility": ([4, 4], [8, 8]),
    "store": ([4, 4], [8, 8]),
}


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

    print("\n[1] JSON INPUT")
    print("Test case:", case_name)
    print("Expected status:", expected_status)

    # 2. Convert only the input section into solver arguments
    solver_arguments = build_solver_arguments(
        input_data,
        TEST_ROOM_SIZE_TABLE
    )

    solver_arguments["max_hallway_segments"] = 6
    solver_arguments["time_limit_seconds"] = 65

    print("\n[2] INPUT ADAPTER")
    print("JSON input successfully converted.")

    # 3. Run P1
    print("\n[3] P1 GEOMETRY SOLVER")
    print("Generating layout...")

    solver_result = solve_layout(**solver_arguments)

    solver_status = solver_result.get("status")

    print("Solver status:", solver_status)
    print("Solver message:", solver_result.get("message"))

    # 4. Run P4 only if P1 succeeds
    validation_errors = []
    validation_warnings = []

    if solver_status == "success":
        print("\n[4] P4 VALIDATION")

        validation_results = validate_solver_result(
            input_data,
            solver_result,
            size_table=TEST_ROOM_SIZE_TABLE,
            check_gaps=True,
        )

        # Separate hard errors from soft warnings
        validation_errors = [
            problem for problem in validation_results
            if problem.get("severity", "error") == "error"
        ]

        validation_warnings = [
            problem for problem in validation_results
            if problem.get("severity") == "warning"
        ]

        validation_passed = len(validation_errors) == 0

        print("P4 status:", "PASSED" if validation_passed else "FAILED")

        if validation_errors:
            print("\nValidation errors:")

            for index, error in enumerate(validation_errors, start=1):
                print(f"{index}. [{error['code']}] {error['message']}")

        if validation_warnings:
            print("\nValidation warnings:")

            for index, warning in enumerate(validation_warnings, start=1):
                print(f"{index}. [{warning['code']}] {warning['message']}")

        if not validation_errors and not validation_warnings:
            print("No validation issues found.")

    else:
        validation_passed = False

        print("\n[4] P4 VALIDATION")
        print("Skipped because P1 did not generate a layout.")
        
    # 5. Determine final status
    if solver_status == "success" and validation_passed:
        final_status = "valid"
    elif solver_status == "infeasible":
        final_status = "infeasible"
    else:
        final_status = "invalid"

    print("\n[5] FINAL RESULT")
    print("P1:", solver_status)
    print("P4:", "PASSED" if validation_passed else "NOT PASSED")
    print("Final status:", final_status)

    if expected_status:
        print("Expected status:", expected_status)
        print(
            "Expectation match:",
            "YES" if final_status == expected_status else "NO"
        )

    if solver_status == "success":
        print("\nGenerated layout:")
        pprint(solver_result)

    return {
        "case": case_name,
        "expected_status": expected_status,
        "solver_status": solver_status,
        "final_status": final_status,
        "expectation_match": (
            final_status == expected_status
            if expected_status else None
        ),
        "validation_passed": validation_passed,
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run a JSON test case through P1 and P4."
    )

    parser.add_argument(
        "json_file",
        help="Path to the JSON test case."
    )

    args = parser.parse_args()
    run_json_file(args.json_file)


if __name__ == "__main__":
    main()
