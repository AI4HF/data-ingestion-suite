#!/usr/bin/env bash
# RED test for the cause-of-death-mapping.json defect (AI4HF/data-ingestion-suite).
#
# Runs the REAL SRDC toFHIR engine (srdc/tofhir-engine docker image) locally,
# file-to-file, against a synthetic single-row DEATH fixture whose OMOP cause
# concept is NOT translatable via omopToIcd10.csv (it carries only
# cause_source_value). No OMOP database, no onFHIR/live cluster involved.
#
# Asserts the produced Observation has a non-empty
# valueCodeableConcept.coding with system http://hl7.org/fhir/sid/icd-10,
# which is what the HFR-CauseOfDeath profile (primaryICD10Code slice, min=1)
# requires for onFHIR to accept it.
#
# Expected on current main: FAIL (valueCodeableConcept is absent entirely).
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
  echo "FAIL: toFHIR produced no output file at all under $OUT_DIR" >&2
  exit 1
fi
echo "output file: $RESOURCE_FILE"

echo "== Asserting valueCodeableConcept.coding is non-empty with system icd-10 =="
python3 "$REPO_ROOT/test/red/assert_coding.py" "$RESOURCE_FILE"
