#!/usr/bin/env bash
# Build downloadable sample cohorts for GTM (10k default; pass 100000 or 1000000).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PATIENTS="${1:-10000}"
SEED="${2:-20260612}"
SAMPLES_DIR="$ROOT/samples"

mkdir -p "$SAMPLES_DIR"
LABEL="${PATIENTS}-patients"
OUT="$SAMPLES_DIR/launch-demo-${LABEL}"

cd "$ROOT"
echo "==> Building launch-demo sample cohort: $PATIENTS patients (seed $SEED)"
atlas launch-demo --patients "$PATIENTS" --seed "$SEED" --out "$OUT"

echo "==> Structural validation"
atlas validate "$OUT"

if [ "$PATIENTS" -le 500 ]; then
  echo "==> GTM fidelity validation (full preset; use smaller N for speed)"
  atlas validate "$OUT" --gtm --min-samples "$((PATIENTS / 4))"
else
  echo "==> Skipping per-module cohort checks at N=$PATIENTS (launch-demo is multi-module; see docs/fidelity-scorecard.md for single-module fidelity)"
fi

echo "==> HTML report"
atlas report "$OUT" --module hypertension --out "$OUT/cohort-report.html"

cp docs/known-limitations.md "$OUT/LIMITATIONS.md"
cp "$OUT/generation-metadata.json" "$OUT/MANIFEST.json"

echo "==> Sample ready at $OUT"
echo "    Zip for release: tar -czf launch-demo-${LABEL}.tar.gz -C samples launch-demo-${LABEL}"
