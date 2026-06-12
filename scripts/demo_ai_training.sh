#!/usr/bin/env bash
# Demo: AI training / evaluation cohort with structured + unstructured data.
# Generates chronic-disease patients with template notes; validates fidelity.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-./demo-ai-training}"
SEED="${2:-42}"
PATIENTS="${3:-500}"

cd "$ROOT"
echo "==> Generating AI training demo cohort ($PATIENTS patients, seed $SEED)"
atlas generate --patients "$PATIENTS" --seed "$SEED" \
  --module hypertension,diabetes,depression,wellness \
  --with-notes --with-sdoh --summary \
  --out "$OUT"

echo "==> Structural validation"
atlas validate "$OUT"

echo "==> Cohort fidelity (hypertension + diabetes)"
atlas validate "$OUT" --cohort --module hypertension --min-samples 200
atlas validate "$OUT" --cohort --module diabetes --min-samples 200

echo "==> Done. Bundles in $OUT (DocumentReference notes embedded per patient)."
