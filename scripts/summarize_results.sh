#!/usr/bin/env bash
set -euo pipefail

INPUT_FILE="${1:-results.jsonl}"

if [[ ! -f "$INPUT_FILE" ]]; then
  echo "Input file not found: $INPUT_FILE" >&2
  exit 1
fi

echo "Summarizing scrape results from ${INPUT_FILE}"
grep '"source_id"' "$INPUT_FILE" \
  | sed -n 's/.*"source_id": "\([^"]*\)".*"status": \(true\|false\).*"latency": \([0-9][0-9]*\).*/\1|\2|\3/p' \
  | sort \
  | awk -F'|' '
      {
        total[$1]++
        latency[$1]+=$3
        if ($2 == "true") {
          success[$1]++
        } else {
          failed[$1]++
        }
      }
      END {
        printf("%-12s %-8s %-8s %-8s %-12s\n", "source_id", "total", "success", "failed", "avg_latency")
        for (source in total) {
          avg = (total[source] > 0) ? latency[source] / total[source] : 0
          printf("%-12s %-8d %-8d %-8d %-12.2f\n", source, total[source], success[source] + 0, failed[source] + 0, avg)
        }
      }
    '
