#!/usr/bin/env python3
"""GREEN assertion for the cause-of-death-mapping.json fix (option a).

FIX CHOSEN: tighten the mapping-entry precondition so a DEATH row carrying
ONLY cause_source_value (no cause_concept_id / cause_source_concept_id) is
no longer emitted as an Observation at all. Such a row has no translatable
OMOP concept, so toFHIR cannot honestly populate the HFR-CauseOfDeath
profile's required (min=1) primaryICD10Code coding without fabricating a
code. Excluding the row turns a 400-refused write (numOfFailedWrites) into
an honest numOfNotMapped -- no resource is produced, none is refused.

This DELIBERATELY changes the expected outcome asserted by
assert_coding.py (which expected a coding to be present). That original
assertion, and its FAIL output proving the pre-fix defect, is preserved
unmodified in git history (see the red commit) and is not deleted here --
this file is a NEW, additional assertion for the new expected behaviour,
not an edit of the old one.

All data referenced here is synthetic (fixture authored for this test only).
"""
import json
import sys


def load_resources(path):
    resources = []
    with open(path) as f:
        text = f.read().strip()
    if not text:
        return resources
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
        print("usage: assert_not_mapped.py <ndjson-or-json-file>", file=sys.stderr)
        sys.exit(2)

    resources = load_resources(sys.argv[1])
    observations = [r for r in resources if r.get("resourceType") == "Observation"]

    if not observations:
        print("PASS: no Observation emitted for the DEATH row carrying only "
              "cause_source_value (row correctly excluded by the "
              "causeExists precondition instead of being emitted incomplete "
              "and refused by onFHIR).")
        sys.exit(0)

    print(f"FAIL: expected 0 Observations for the untranslatable-cause row, "
          f"found {len(observations)}.")
    sys.exit(1)


if __name__ == "__main__":
    main()
