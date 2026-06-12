#!/usr/bin/env bash
# Demo: FHIR integration testing — US Core bundles + NDJSON + providers/coverage/SDoH.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-./demo-fhir-integration}"
SEED="${2:-7}"
PATIENTS="${3:-200}"

cd "$ROOT"
echo "==> Generating FHIR integration demo ($PATIENTS patients)"
atlas generate --patients "$PATIENTS" --seed "$SEED" \
  --module hypertension,diabetes,asthma,pediatric_wellness \
  --with-coverage --with-providers --with-sdoh --with-claims \
  --summary --out "$OUT"

echo "==> Structural validation"
atlas validate "$OUT"

echo "==> NDJSON export (Bulk Data style)"
NDJSON_OUT="${OUT}-ndjson"
atlas generate --patients "$PATIENTS" --seed "$SEED" \
  --module hypertension,diabetes \
  --with-coverage --with-providers --with-sdoh \
  --format ndjson --out "$NDJSON_OUT"

echo "==> Done."
echo "    Bundles: $OUT"
echo "    NDJSON:  $NDJSON_OUT"
