#!/usr/bin/env bash
# Script 2: summarize_results.sh
# Purpose: Summarizes a results.jsonl file by source, success rate, and average latency.
# Key features: variables, pipes, grep, sed, sort, awk
# Usage: bash scripts/summarize_results.sh results.jsonl

# --- Variables ---
RESULTS_FILE="${1:-results.jsonl}"

if [ ! -f "$RESULTS_FILE" ]; then
    echo "Error: File not found: $RESULTS_FILE"
    echo "Usage: bash scripts/summarize_results.sh <results.jsonl>"
    exit 1
fi

echo "========================================"
echo "Results Summary: $RESULTS_FILE"
echo "========================================"

# Total record count
TOTAL=$(grep -c "source_id" "$RESULTS_FILE")
echo "Total records : $TOTAL"
echo ""

# Per-source breakdown using grep, sed, sort, and awk
echo "--- By Source ---"
echo ""

# Extract all unique source_ids using grep and sed, then sort
SOURCES=$(grep -o '"source_id": *"[^"]*"' "$RESULTS_FILE" \
    | sed 's/"source_id": *"//;s/"//' \
    | sort -u)

for SOURCE in $SOURCES; do
    # Filter lines for this source using grep
    SOURCE_LINES=$(grep "\"source_id\": *\"${SOURCE}\"" "$RESULTS_FILE")

    # Count total tasks for this source
    COUNT=$(echo "$SOURCE_LINES" | grep -c "source_id")

    # Count successes (success: true)
    SUCCESS_COUNT=$(echo "$SOURCE_LINES" | grep -c '"success": *true')

    # Count failures (success: false)
    FAIL_COUNT=$(echo "$SOURCE_LINES" | grep -c '"success": *false')

    # Calculate success rate using awk
    SUCCESS_RATE=$(awk -v s="$SUCCESS_COUNT" -v t="$COUNT" \
        'BEGIN { if (t > 0) printf "%.1f", (s / t) * 100; else print "N/A" }')

    # Extract latency values and compute average using grep, sed, and awk
    AVG_LATENCY=$(echo "$SOURCE_LINES" \
        | grep -o '"latency_ms": *[0-9]*' \
        | sed 's/"latency_ms": *//' \
        | awk '{ sum += $1; count++ } END { if (count > 0) printf "%.1f", sum / count; else print "N/A" }')

    # Extract min/max latency using sort and awk
    MIN_LATENCY=$(echo "$SOURCE_LINES" \
        | grep -o '"latency_ms": *[0-9]*' \
        | sed 's/"latency_ms": *//' \
        | sort -n \
        | awk 'NR==1 { print }')

    MAX_LATENCY=$(echo "$SOURCE_LINES" \
        | grep -o '"latency_ms": *[0-9]*' \
        | sed 's/"latency_ms": *//' \
        | sort -n \
        | awk 'END { print }')

    echo "Source      : $SOURCE"
    echo "  Tasks     : $COUNT"
    echo "  Succeeded : $SUCCESS_COUNT"
    echo "  Failed    : $FAIL_COUNT"
    echo "  Success % : ${SUCCESS_RATE}%"
    echo "  Latency   : avg=${AVG_LATENCY}ms  min=${MIN_LATENCY}ms  max=${MAX_LATENCY}ms"
    echo ""
done

echo "========================================"

# Overall success rate across all sources using awk
TOTAL_SUCCESS=$(grep -c '"success": *true' "$RESULTS_FILE")
TOTAL_FAIL=$(grep -c '"success": *false' "$RESULTS_FILE")
OVERALL_RATE=$(awk -v s="$TOTAL_SUCCESS" -v t="$TOTAL" \
    'BEGIN { if (t > 0) printf "%.1f", (s / t) * 100; else print "N/A" }')

echo "Overall"
echo "  Total     : $TOTAL"
echo "  Succeeded : $TOTAL_SUCCESS"
echo "  Failed    : $TOTAL_FAIL"
echo "  Success % : ${OVERALL_RATE}%"
echo "========================================"
