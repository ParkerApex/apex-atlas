#!/usr/bin/env bash
# Demo: Payer / quality-measure testing with MeasureReports, claims, and coverage.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-./demo-quality-measures}"
SEED="${2:-99}"
PATIENTS="${3:-1000}"

cd "$ROOT"
echo "==> Generating quality-measures demo ($PATIENTS patients)"
atlas generate --patients "$PATIENTS" --seed "$SEED" \
  --module hypertension,diabetes,wellness,pediatric_wellness,adult_immunizations \
  --with-coverage --with-claims --with-measures --summary \
  --out "$OUT"

echo "==> Structural validation"
atlas validate "$OUT"

MEASURE_COUNT="$(find "$OUT" -name 'MeasureReport-*.json' 2>/dev/null | wc -l | tr -d ' ')"
echo "==> MeasureReport summary files: $MEASURE_COUNT"

echo "==> Done. Individual + population MeasureReports in $OUT"
