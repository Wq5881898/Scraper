#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"
TEST_DIR="${TEST_DIR:-tests}"
LOG_DIR="${LOG_DIR:-logs}"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/test_run_${STAMP}.log"

mkdir -p "$LOG_DIR"

echo "Running unit tests from ${TEST_DIR}"
"$PYTHON_BIN" -m unittest discover -s "$TEST_DIR" -v 2>&1 | tee "$LOG_FILE"

echo
echo "Filtered summary from ${LOG_FILE}"
sed 's/\r$//' "$LOG_FILE" \
  | grep -E '^(test_|Ran |OK|FAILED)' \
  | awk '
      /^test_/ { print $0 }
      /^Ran / { ran=$2 }
      /^OK/ { status="OK" }
      /^FAILED/ { status="FAILED" }
      END {
        if (status == "") {
          status = "UNKNOWN"
        }
        printf("tests_ran=%s final_status=%s\n", ran, status)
      }
    '
