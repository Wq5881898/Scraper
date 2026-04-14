# Multithreading Benchmark

This benchmark compares scraper performance under different thread settings using the existing application flow.

## Purpose

The script is intended to support Phase 4 Part C by comparing:

- single-thread execution
- medium multithread execution
- higher multithread execution

using the same address list and scraper pipeline.

## File

- `tests/benchmark_multithread.py`

## Default benchmark cases

- `single-thread`: `max_workers=1`, `initial_limit=1`
- `medium-thread`: `max_workers=4`, `initial_limit=2`

## Default inputs

- address list: `config/testlist.txt`
- curl config: `config/curl_config.txt`
- address limit: `3`
- sources: `web2`

## Metrics collected

- total run time
- total records
- success count
- failure count
- success rate
- average latency
- throughput (records per second)

## How to run

```powershell
.\.venv\Scripts\activate
python tests\benchmark_multithread.py
```

## Output

The script:

- prints a benchmark table to the terminal
- saves per-run JSONL files under `testdata/benchmarks/`
- saves an aggregated summary JSON file at `testdata/benchmarks/benchmark_summary.json`
