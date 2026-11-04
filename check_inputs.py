"""Check every test input file. Usage: python check_inputs.py [folder] [schema]"""
from pathlib import Path

import glob, json, sys
from jsonschema import Draft202012Validator

folder = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(__file__).parent / "tests" / "TestCases"
)
schema_path = (
    Path(sys.argv[2])
    if len(sys.argv) > 2
    else Path(__file__).parent / "input_schema.json"
)
schema = json.load(open(schema_path))
validator = Draft202012Validator(schema)
STATUSES = {"valid", "infeasible", "conflict", "pending"}

files = sorted(glob.glob(f"{folder}/*.json"))
problems = 0
for path in files:
    errors = []
    try:
        data = json.load(open(path))
    except json.JSONDecodeError as e:
        print(f"FAIL {path}: not valid JSON ({e})"); problems += 1; continue
    inp = data.get("input", {})
    errors += [f"schema: {e.message}" for e in validator.iter_errors(inp)]
    names = [r.get("name") for r in inp.get("rooms", [])]
    for n in {n for n in names if names.count(n) > 1}:
        errors.append(f"duplicate room name: {n}")
    for p in inp.get("pins", []):
        if p.get("room") not in names:
            errors.append(f"pin refers to unknown room: {p.get('room')}")
    types = {r.get("name"): r.get("type") for r in inp.get("rooms", [])}
    for r in inp.get("rooms", []):
        target = r.get("attached_to")
        if target is None:
            continue
        if r.get("type") != "bathroom":
            errors.append(f"only a bathroom can use attached_to: {r.get('name')}")
        elif types.get(target) != "bedroom":
            errors.append(f"attached_to must name a bedroom: {r.get('name')} -> {target}")
    status = data.get("expect", {}).get("status", "").lower()
    if status not in STATUSES:
        errors.append(f"unknown expected status: {data.get('expect', {}).get('status')!r}")
    elif data.get("expect", {}).get("status") != status:
        errors.append(f"status must be lowercase: {data['expect']['status']!r}")
    if errors:
        problems += 1
        print(f"FAIL {path}")
        for e in errors: print("   -", e)
    else:
        print(f"ok   {path}")
print(f"\n{len(files)} files, {problems} with problems")
