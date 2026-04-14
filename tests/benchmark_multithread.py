from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import (
    DEFAULT_ADDRESS_LIST_PATH,
    DEFAULT_CURL_CONFIG_PATH,
)
from main import run_demo
from src.results_reader import summarize_results


def _build_default_configs() -> list[dict[str, Any]]:
    return [
        {
            "label": "single-thread",
            "max_workers": 1,
            "initial_limit": 1,
        },
        {
            "label": "medium-thread",
            "max_workers": 4,
            "initial_limit": 2,
        },
    ]


def _run_one_benchmark(
    *,
    label: str,
    addresses_path: str,
    curl_config_path: str,
    results_path: str,
    qps: float,
    max_workers: int,
    initial_limit: int,
    limit: int,
    selected_sources: list[str],
) -> dict[str, Any]:
    results_file = Path(results_path)
    if results_file.exists():
        results_file.unlink()

    start = time.perf_counter()
    run_demo(
        address_list_path=addresses_path,
        curl_config_path=curl_config_path,
        results_path=results_path,
        qps=qps,
        max_workers=max_workers,
        initial_limit=initial_limit,
        limit=limit,
        selected_sources=selected_sources,
    )
    elapsed = time.perf_counter() - start

    summary = summarize_results(results_path)
    total_records = summary["total_records"]
    overall = summary["overall"]
    throughput = total_records / elapsed if elapsed > 0 else 0.0

    return {
        "label": label,
        "results_path": results_path,
        "sources": selected_sources,
        "qps": qps,
        "max_workers": max_workers,
        "initial_limit": initial_limit,
        "address_limit": limit,
        "elapsed_sec": round(elapsed, 3),
        "total_records": total_records,
        "success_count": overall["successes"],
        "failure_count": overall["failures"],
        "success_rate_pct": round(overall["success_rate_pct"], 2),
        "avg_latency_ms": round(overall["avg_latency_ms"], 2),
        "throughput_rps": round(throughput, 3),
        "invalid_lines": summary["invalid_lines"],
    }


def _print_report(results: list[dict[str, Any]]) -> None:
    print()
    print("Multithreading Benchmark Results")
    print("-" * 108)
    print(
        f"{'Label':<18}"
        f"{'Workers':>8}"
        f"{'Init':>8}"
        f"{'Records':>10}"
        f"{'Success':>10}"
        f"{'Fail':>8}"
        f"{'Time(s)':>10}"
        f"{'Avg Lat(ms)':>14}"
        f"{'Req/s':>10}"
    )
    print("-" * 108)
    for item in results:
        print(
            f"{item['label']:<18}"
            f"{item['max_workers']:>8}"
            f"{item['initial_limit']:>8}"
            f"{item['total_records']:>10}"
            f"{item['success_count']:>10}"
            f"{item['failure_count']:>8}"
            f"{item['elapsed_sec']:>10.3f}"
            f"{item['avg_latency_ms']:>14.2f}"
            f"{item['throughput_rps']:>10.3f}"
        )
    print("-" * 108)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a simple benchmark comparing single-thread and multithread scraper performance."
    )
    parser.add_argument("--addresses", default=DEFAULT_ADDRESS_LIST_PATH, help="Path to the address list file.")
    parser.add_argument("--curl-config", default=DEFAULT_CURL_CONFIG_PATH, help="Path to the curl config file.")
    parser.add_argument("--output-dir", default="testdata/benchmarks", help="Directory for benchmark result files.")
    parser.add_argument("--qps", type=float, default=2.0, help="Global QPS limit used during benchmarking.")
    parser.add_argument("--limit", type=int, default=3, help="Number of addresses to benchmark.")
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["web2"],
        help="Sources to benchmark, for example: web1 web2",
    )
    parser.add_argument(
        "--save-json",
        default="testdata/benchmarks/benchmark_summary.json",
        help="Path to save aggregated benchmark results as JSON.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for config in _build_default_configs():
        results_path = output_dir / f"{config['label']}.jsonl"
        benchmark_result = _run_one_benchmark(
            label=config["label"],
            addresses_path=args.addresses,
            curl_config_path=args.curl_config,
            results_path=str(results_path),
            qps=args.qps,
            max_workers=config["max_workers"],
            initial_limit=config["initial_limit"],
            limit=args.limit,
            selected_sources=args.sources,
        )
        results.append(benchmark_result)

    _print_report(results)

    save_path = Path(args.save_json)
    if save_path.parent and str(save_path.parent) not in {".", ""}:
        save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Saved benchmark summary to: {save_path}")


if __name__ == "__main__":
    main()
