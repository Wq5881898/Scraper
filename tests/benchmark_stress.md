# Stress Benchmark

This benchmark is designed to show a clearer difference between single-thread and multi-thread execution than the basic benchmark.

## Purpose

The standard benchmark keeps the application's normal request speed controls. That result is useful because it shows real behavior under normal protection rules. This stress benchmark has a different goal:

- increase the workload size
- reduce or remove rate limiting during the test
- repeat the same workload for several rounds
- record CPU and memory usage for later charts
- record status codes, error types, and backoff triggers

This makes the time gap between single-thread and multi-thread runs easier to see.

## Default Setup

- source: `web2`
- tasks per round: `100`
- rounds: `1`
- total repeated workload: about `100` requests for one source
- QPS: `0.0` by default, which disables rate limiting in the benchmark
- if the address list is shorter than the task count, the script repeats addresses automatically

## Compared Configurations

- `single-thread-stress`
  - `max_workers=1`
  - `initial_limit=1`
- `low-thread-stress`
  - `max_workers=2`
  - `initial_limit=2`
- `medium-thread-stress`
  - `max_workers=4`
  - `initial_limit=4`
- `high-thread-stress`
  - `max_workers=8`
  - `initial_limit=8`
- `very-high-thread-stress`
  - `max_workers=16`
  - `initial_limit=16`
- `extreme-thread-stress`
  - `max_workers=32`
  - `initial_limit=32`
- `ultra-thread-stress`
  - `max_workers=64`
  - `initial_limit=64`
- `max-thread-stress`
  - `max_workers=128`
  - `initial_limit=128`

## Collected Metrics

- total execution time
- total records
- success count
- failure count
- average latency
- throughput
- average CPU usage
- peak CPU usage
- average memory usage
- peak memory usage
- status code counts
- error type counts
- HTTP 429 count
- HTTP 403 count
- timeout count
- connection error count
- backoff trigger count
- backoff error type counts

## Run Command

```powershell
python tests\benchmark_stress.py --sources web2 --limit 100 --rounds 1
```

## Output Files

- round-by-round JSONL results:
  - `testdata/stress_benchmarks/<label>/`
- summary JSON:
  - `testdata/stress_benchmarks/stress_benchmark_summary.json`

## Notes

- If `psutil` is installed, the script records CPU and memory usage.
- If `psutil` is not installed, the benchmark still runs, but resource metrics are skipped.
- This test is meant for performance comparison, not for normal day-to-day scraper runs.
- It can also help estimate at which concurrency level the target site starts returning rate-limit or error signals.
