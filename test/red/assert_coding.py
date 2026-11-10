#!/usr/bin/env python3
"""RED assertion for the cause-of-death-mapping.json defect.

Reads the toFHIR-produced Observation for the synthetic fixture row and
asserts valueCodeableConcept.coding is non-empty and contains a coding with
system == http://hl7.org/fhir/sid/icd-10 (the HFR-CauseOfDeath
primaryICD10Code slice requirement).

All data referenced here is synthetic (fixture authored for this test only).
"""
import json
import sys

ICD10_SYSTEM = "http://hl7.org/fhir/sid/icd-10"


def load_resources(path):
    resources = []
    with open(path) as f:
        text = f.read().strip()
    if not text:
        return resources
    # ndjson: one resource per line; also tolerate a single JSON array/object.
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            return obj
        return [obj]
    except json.JSONDecodeError:
        for line in text.splitlines():
            line = line.strip()
            if line:
                resources.append(json.loads(line))
        return resources


def main():
    if len(sys.argv) != 2:
        print("usage: assert_coding.py <ndjson-or-json-file>", file=sys.stderr)
        sys.exit(2)

    resources = load_resources(sys.argv[1])
    observations = [r for r in resources if r.get("resourceType") == "Observation"]

    if not observations:
        print(f"FAIL: expected 1 Observation, found {len(observations)} "
              f"among {len(resources)} resource(s)")
        sys.exit(1)

    if len(observations) != 1:
        print(f"FAIL: expected exactly 1 Observation for the single fixture "
              f"row, found {len(observations)}")
        sys.exit(1)

    obs = observations[0]
    vcc = obs.get("valueCodeableConcept")
    coding = (vcc or {}).get("coding") if isinstance(vcc, dict) else None

    icd10_codings = [
        c for c in (coding or [])
        if isinstance(c, dict) and c.get("system") == ICD10_SYSTEM
    ]

    if icd10_codings:
        print(f"PASS: valueCodeableConcept.coding has {len(icd10_codings)} "
              f"coding(s) with system {ICD10_SYSTEM}")
        sys.exit(0)

    print("FAIL: valueCodeableConcept.coding has no coding with system "
          f"{ICD10_SYSTEM} for a DEATH row carrying only cause_source_value.")
    print(f"  valueCodeableConcept present: {vcc is not None}")
    print(f"  coding array: {coding!r}")
    print("  This is exactly the onFHIR-refusal defect: HFR-CauseOfDeath "
          "requires Observation.value[x] min=1, .coding min=1, slice "
          "primaryICD10Code min=1, system fixed to "
          f"{ICD10_SYSTEM}. The mapping's valueCodeableConcept.coding "
          "expression only reads cause_concept_id / cause_source_concept_id "
          "via trms:translateToCoding(...); it never falls back to "
          "cause_source_value, even though the mapping-entry precondition "
          "admits rows carrying only cause_source_value.")
    sys.exit(1)


if __name__ == "__main__":
    main()
