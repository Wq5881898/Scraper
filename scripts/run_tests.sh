#!/usr/bin/env bash
# Script 1: run_tests.sh
# Purpose: Automates unit test execution, writes a timestamped log, and prints a compact summary.
# Key features: variables, pipes, tee, sed, grep, awk
# Usage: bash scripts/run_tests.sh

# --- Variables ---
LOG_DIR="logs"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${LOG_DIR}/test_run_${TIMESTAMP}.log"
PYTHON_CMD="python3"

# Create log directory if it does not exist
mkdir -p "$LOG_DIR"

echo "Running unit tests..."
echo "Log file: $LOG_FILE"
echo "========================================"

# Run tests, capture output with tee (writes to both terminal and log file)
$PYTHON_CMD -m unittest discover -s tests -v 2>&1 | tee "$LOG_FILE"

echo "========================================"
echo "Test Summary"
echo "========================================"

# Parse the log for results using grep, sed, and awk
RESULT_LINE=$(grep -E "^(OK|FAILED|ERROR)" "$LOG_FILE" | tail -1)

# Count individual test outcomes using grep and awk
TOTAL=$(grep -c "^\.\.\." "$LOG_FILE" 2>/dev/null || grep -oP "Ran \K[0-9]+" "$LOG_FILE" | tail -1)
PASSED=$(grep -c " \.\.\. ok$" "$LOG_FILE" 2>/dev/null || echo 0)
FAILED=$(grep -c " \.\.\. FAIL$" "$LOG_FILE" 2>/dev/null || echo 0)
ERRORS=$(grep -c " \.\.\. ERROR$" "$LOG_FILE" 2>/dev/null || echo 0)
SKIPPED=$(grep -c " \.\.\. skipped " "$LOG_FILE" 2>/dev/null || echo 0)

# Use awk to extract the total run count from the summary line
RAN=$(grep "^Ran " "$LOG_FILE" | awk '{print $2}')
TIME_TAKEN=$(grep "^Ran " "$LOG_FILE" | awk '{print $5}')

echo "Tests ran   : ${RAN:-0}"
echo "Passed      : $(grep -c "ok$" "$LOG_FILE")"
echo "Failed      : $(grep -c "^FAIL:" "$LOG_FILE")"
echo "Errors      : $(grep -c "^ERROR:" "$LOG_FILE")"
echo "Skipped     : $SKIPPED"
echo "Time (s)    : ${TIME_TAKEN:-N/A}"
echo "----------------------------------------"

# Print overall result, coloring output using sed substitution
echo "$RESULT_LINE" | sed 's/^OK/RESULT: ALL PASSED/' | sed 's/^FAILED/RESULT: SOME FAILED/'

echo "Full log saved to: $LOG_FILE"
