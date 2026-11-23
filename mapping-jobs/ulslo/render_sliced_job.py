#!/usr/bin/env python3
"""Render a single person-ordinal SLICE of the ulslo-deploy toFHIR job.

WHY: toFHIR accumulates its whole mapped result set before writing (no
streaming path - see slice-plan.json._comment). Spark JDBC partitioning does
not bound memory. The only lever is SqlSource.query with an explicit
row-range predicate, so this script rewrites the named mapping's whole-table
`tableName` SqlSource bindings into `query` bindings bounded to one ordinal
slice of persons - never a raw person_id value, only a ROW_NUMBER() ordinal
range, so slice boundaries are never patient-identifying.

Output: one complete toFHIR mapping-job JSON, containing ONLY the requested
mapping (job id suffixed `-slice-<n>` so it deploys as its own toFHIR job,
independently retriable), to stdout.

Usage:
  render_sliced_job.py --deploy ulslo-deploy.json --plan slice-plan.json \
      --mapping procedure-mapping --slice-index 3 [--only-source procedure_occurrence]
"""
import argparse
import copy
import json
import sys


def sliced_query(table: str, start_ordinal: int, end_ordinal: int) -> str:
    # start_ordinal/end_ordinal are 1-based INCLUSIVE ordinal positions over
    # persons ordered by person_id - never a person_id literal.
    return (
        "SELECT s.* FROM omop_ai4hf_mv.{table} s "
        "JOIN ("
        "  SELECT person_id, row_number() OVER (ORDER BY person_id) AS rn "
        "  FROM omop_ai4hf_mv.person"
        ") o ON o.person_id = s.person_id "
        "WHERE o.rn BETWEEN {start} AND {end}"
    ).format(table=table, start=start_ordinal, end=end_ordinal)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--mapping", required=True, help="mapping `name` field, e.g. procedure-mapping")
    ap.add_argument("--slice-index", type=int, required=True, help="0-based slice index")
    args = ap.parse_args()

    deploy = json.load(open(args.deploy))
    plan = json.load(open(args.plan))

    plan_entry = plan["mappings"].get(args.mapping)
    if plan_entry is None:
        print(f"error: {args.mapping!r} not in slice-plan.json", file=sys.stderr)
        return 1
    if not plan_entry.get("sliced"):
        print(f"error: {args.mapping!r} is not marked sliced in slice-plan.json - run it whole", file=sys.stderr)
        return 1

    width = plan_entry["bucket_width_persons"]
    slice_count = plan_entry["slice_count"]
    if not (0 <= args.slice_index < slice_count):
        print(f"error: slice-index {args.slice_index} out of range [0,{slice_count})", file=sys.stderr)
        return 1

    cohort_persons = plan["cohort_persons"]
    start_ordinal = args.slice_index * width + 1
    end_ordinal = min((args.slice_index + 1) * width, cohort_persons)

    mapping_src = next((m for m in deploy["mappings"] if m["name"] == args.mapping), None)
    if mapping_src is None:
        print(f"error: {args.mapping!r} not found in {args.deploy}", file=sys.stderr)
        return 1

    sliced_mapping = copy.deepcopy(mapping_src)
    for alias, binding in sliced_mapping["sourceBinding"].items():
        table = binding.pop("tableName", None)
        if table is None:
            continue  # already query-based; leave as-is
        binding["query"] = sliced_query(table, start_ordinal, end_ordinal)

    out = copy.deepcopy(deploy)
    out["id"] = f"{deploy['id']}-{args.mapping}-slice-{args.slice_index:03d}"
    out["name"] = f"{deploy['name']}-{args.mapping}-slice-{args.slice_index:03d}"
    out["mappings"] = [sliced_mapping]

    json.dump(out, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
