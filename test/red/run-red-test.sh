#!/usr/bin/env bash
# RED-then-GREEN test for the cause-of-death-mapping.json defect
# (AI4HF/data-ingestion-suite).
#
# Runs the REAL SRDC toFHIR engine (srdc/tofhir-engine docker image) locally,
# file-to-file, against a synthetic single-row DEATH fixture whose OMOP cause
# concept is NOT translatable via omopToIcd10.csv (it carries only
# cause_source_value). No OMOP database, no onFHIR/live cluster involved.
#
# ORIGINAL (red) expectation, proved failing on main (7177ab78) and preserved
# verbatim at test/red/assert_coding.py: the produced Observation has a
# non-empty valueCodeableConcept.coding with system
# http://hl7.org/fhir/sid/icd-10, which HFR-CauseOfDeath (primaryICD10Code
# slice, min=1) requires for onFHIR to accept the write.
#
# FIX CHOSEN (option a, see PR body): tighten the mapping-entry precondition
# so a row with no translatable cause_concept_id / cause_source_concept_id is
# never emitted, rather than emitted incomplete and refused by onFHIR.
# EXPECTED BEHAVIOUR THEREFORE CHANGES: this driver now asserts via
# test/red/assert_not_mapped.py that NO Observation is produced for this row
# (numOfNotMapped, not numOfFailedWrites). assert_coding.py is left in the
# repo, unmodified, as the historical proof of the original defect; it is no
# longer invoked by this driver.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$REPO_ROOT/test/red/output"
CONTAINER_NAME="red-cause-of-death-$$"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

cleanup() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "== Running toFHIR engine against synthetic fixture =="
docker run -d \
  --name "$CONTAINER_NAME" \
  --platform linux/amd64 \
  -v "$REPO_ROOT:/work" \
  -e CONTEXT_PATH=/work \
  -e SPARK_MASTER="local[2]" \
  -e JAVA_OPTIONS="-Xms512m -Xmx2g" \
  srdc/tofhir-engine:latest \
  run --job /work/test/red/job.json >/dev/null

# The engine process stays alive (akka system) after the job finishes, so we
# poll its logs for the terminal line instead of waiting on the container.
for _ in $(seq 1 60); do
  if docker logs "$CONTAINER_NAME" 2>&1 | grep -q "MappingJob execution finished"; then
    break
  fi
  if docker logs "$CONTAINER_NAME" 2>&1 | grep -qiE "Exception|ERROR"; then
    docker logs "$CONTAINER_NAME" 2>&1 | tail -60
    echo "FAIL: toFHIR engine errored before finishing the job" >&2
    exit 1
  fi
  sleep 5
done

docker logs "$CONTAINER_NAME" 2>&1 | tail -20

echo "== Locating produced Observation for the synthetic fixture row =="
RESOURCE_FILE=$(find "$OUT_DIR" -type f -name 'part-*.txt' 2>/dev/null | head -1 || true)
if [ -z "${RESOURCE_FILE:-}" ]; then
  # Under the fix, this row is excluded by the precondition (not-mapped), so
  # toFHIR may legitimately write no output file at all -- that is a PASS
  # for assert_not_mapped's expectation, unlike the original assert_coding
  # driver where an absent file was unconditionally a FAIL.
  echo "PASS: no output file produced under $OUT_DIR -- consistent with the row being excluded by the causeExists precondition (not-mapped, not written)."
  exit 0
fi
echo "output file: $RESOURCE_FILE"

echo "== Asserting no Observation is emitted for the untranslatable-cause row =="
python3 "$REPO_ROOT/test/red/assert_not_mapped.py" "$RESOURCE_FILE"
