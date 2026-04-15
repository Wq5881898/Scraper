from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency for local benchmarking
    psutil = None

from main import DEFAULT_ADDRESS_LIST_PATH, DEFAULT_CURL_CONFIG_PATH, run_demo
from src import backoff as backoff_module
from src.results_reader import iter_results, summarize_results


def _build_default_configs() -> list[dict[str, Any]]:
    return [
        {
            "label": "single-thread-stress",
            "max_workers": 1,
            "initial_limit": 1,
        },
        {
            "label": "low-thread-stress",
            "max_workers": 2,
            "initial_limit": 2,
        },
        {
            "label": "medium-thread-stress",
            "max_workers": 4,
            "initial_limit": 4,
        },
        {
            "label": "high-thread-stress",
            "max_workers": 8,
            "initial_limit": 8,
        },
        {
            "label": "very-high-thread-stress",
            "max_workers": 16,
            "initial_limit": 16,
        },
        {
            "label": "extreme-thread-stress",
            "max_workers": 32,
            "initial_limit": 32,
        },
        {
            "label": "ultra-thread-stress",
            "max_workers": 64,
            "initial_limit": 64,
        },
        {
            "label": "max-thread-stress",
            "max_workers": 128,
            "initial_limit": 128,
        },
    ]


class _ResourceMonitor:
    def __init__(self, *, sample_interval: float = 0.2) -> None:
        self.sample_interval = sample_interval
        self.samples: list[dict[str, float]] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._process = psutil.Process() if psutil else None

    def start(self) -> None:
        if not self._process:
            return
        self._process.cpu_percent(interval=None)
        self._thread = threading.Thread(target=self._run, name="benchmark-resource-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, float | None]:
        if not self._process:
            return {
                "avg_cpu_pct": None,
                "peak_cpu_pct": None,
                "avg_memory_mb": None,
                "peak_memory_mb": None,
                "sample_count": 0,
            }

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

        if not self.samples:
            return {
                "avg_cpu_pct": 0.0,
                "peak_cpu_pct": 0.0,
                "avg_memory_mb": 0.0,
                "peak_memory_mb": 0.0,
                "sample_count": 0,
            }

        cpu_values = [item["cpu_pct"] for item in self.samples]
        mem_values = [item["memory_mb"] for item in self.samples]
        return {
            "avg_cpu_pct": round(sum(cpu_values) / len(cpu_values), 2),
            "peak_cpu_pct": round(max(cpu_values), 2),
            "avg_memory_mb": round(sum(mem_values) / len(mem_values), 2),
            "peak_memory_mb": round(max(mem_values), 2),
            "sample_count": len(self.samples),
        }

    def _run(self) -> None:
        assert self._process is not None
        while not self._stop_event.is_set():
            time.sleep(self.sample_interval)
            try:
                cpu_pct = self._process.cpu_percent(interval=None)
                memory_mb = self._process.memory_info().rss / (1024 * 1024)
            except (psutil.Error, OSError):
                break
            self.samples.append(
                {
                    "timestamp": time.time(),
                    "cpu_pct": cpu_pct,
                    "memory_mb": round(memory_mb, 2),
                }
            )


class _BackoffMonitor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.events: list[dict[str, Any]] = []
        self._original = backoff_module.BackoffStrategy.get_sleep

    def __enter__(self) -> "_BackoffMonitor":
        def wrapped(instance: Any, attempt: int, error_type: str | None = None) -> float:
            sleep_value = self._original(instance, attempt, error_type)
            with self._lock:
                self.events.append(
                    {
                        "timestamp": time.time(),
                        "attempt": attempt,
                        "error_type": error_type,
                        "sleep_seconds": round(sleep_value, 4),
                    }
                )
            return sleep_value

        backoff_module.BackoffStrategy.get_sleep = wrapped
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        backoff_module.BackoffStrategy.get_sleep = self._original

    def summary(self) -> dict[str, Any]:
        error_counter = Counter(
            (event["error_type"] or "unknown") for event in self.events
        )
        return {
            "trigger_count": len(self.events),
            "error_type_counts": dict(sorted(error_counter.items())),
            "events": self.events,
        }


def _load_address_pool(path: str) -> list[str]:
    addresses: list[str] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                addresses.append(stripped)
    if not addresses:
        raise ValueError(f"No addresses found in {path}")
    return addresses


def _write_expanded_address_file(source_path: str, output_path: str, total_count: int) -> None:
    address_pool = _load_address_pool(source_path)
    target = Path(output_path)
    if target.parent and str(target.parent) not in {".", ""}:
        target.parent.mkdir(parents=True, exist_ok=True)

    with open(target, "w", encoding="utf-8") as handle:
        for index in range(total_count):
            handle.write(address_pool[index % len(address_pool)])
            handle.write("\n")


def _analyze_result_rows(results_path: str) -> dict[str, Any]:
    rows, invalid_lines = iter_results(results_path)
    status_counter: Counter[str] = Counter()
    error_counter: Counter[str] = Counter()
    timeout_count = 0
    conn_error_count = 0
    http_429_count = 0
    http_403_count = 0

    for row in rows:
        status_code = row.get("status_code")
        if status_code is not None:
            status_counter[str(status_code)] += 1
            if status_code == 429:
                http_429_count += 1
            elif status_code == 403:
                http_403_count += 1

        error_type = row.get("error_type")
        if error_type:
            error_name = str(error_type)
            lowered = error_name.lower()
            error_counter[error_name] += 1
            if "timeout" in lowered:
                timeout_count += 1
            elif "connection" in lowered or lowered.startswith("connect"):
                conn_error_count += 1

    return {
        "status_code_counts": dict(sorted(status_counter.items())),
        "error_type_counts": dict(sorted(error_counter.items())),
        "http_429_count": http_429_count,
        "http_403_count": http_403_count,
        "timeout_count": timeout_count,
        "conn_error_count": conn_error_count,
        "invalid_lines": invalid_lines,
    }


def _run_single_round(
    *,
    round_index: int,
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
    expanded_addresses_path = str(results_file.with_name(f"{results_file.stem}-addresses.txt"))
    _write_expanded_address_file(addresses_path, expanded_addresses_path, limit)

    try:
        with _BackoffMonitor() as backoff_monitor:
            start = time.perf_counter()
            run_demo(
                address_list_path=expanded_addresses_path,
                curl_config_path=curl_config_path,
                results_path=results_path,
                qps=qps,
                max_workers=max_workers,
                initial_limit=initial_limit,
                limit=limit,
                selected_sources=selected_sources,
            )
            elapsed = time.perf_counter() - start
    finally:
        expanded_file = Path(expanded_addresses_path)
        if expanded_file.exists():
            expanded_file.unlink()

    summary = summarize_results(results_path)
    overall = summary["overall"]
    result_analysis = _analyze_result_rows(results_path)
    backoff_summary = backoff_monitor.summary()

    return {
        "round": round_index,
        "elapsed_sec": round(elapsed, 3),
        "total_records": summary["total_records"],
        "success_count": overall["successes"],
        "failure_count": overall["failures"],
        "success_rate_pct": round(overall["success_rate_pct"], 2),
        "avg_latency_ms": round(overall["avg_latency_ms"], 2),
        "invalid_lines": summary["invalid_lines"],
        "status_code_counts": result_analysis["status_code_counts"],
        "error_type_counts": result_analysis["error_type_counts"],
        "http_429_count": result_analysis["http_429_count"],
        "http_403_count": result_analysis["http_403_count"],
        "timeout_count": result_analysis["timeout_count"],
        "conn_error_count": result_analysis["conn_error_count"],
        "backoff": backoff_summary,
        "results_path": results_path,
    }


def _run_stress_benchmark(
    *,
    label: str,
    rounds: int,
    addresses_path: str,
    curl_config_path: str,
    output_dir: Path,
    qps: float,
    max_workers: int,
    initial_limit: int,
    limit: int,
    selected_sources: list[str],
    sample_interval: float,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    monitor = _ResourceMonitor(sample_interval=sample_interval)
    round_results: list[dict[str, Any]] = []

    benchmark_start = time.perf_counter()
    monitor.start()
    try:
        for round_index in range(1, rounds + 1):
            results_path = output_dir / f"{label}-round-{round_index:02d}.jsonl"
            round_result = _run_single_round(
                round_index=round_index,
                addresses_path=addresses_path,
                curl_config_path=curl_config_path,
                results_path=str(results_path),
                qps=qps,
                max_workers=max_workers,
                initial_limit=initial_limit,
                limit=limit,
                selected_sources=selected_sources,
            )
            round_results.append(round_result)
    finally:
        resource_stats = monitor.stop()

    total_elapsed = time.perf_counter() - benchmark_start
    total_records = sum(item["total_records"] for item in round_results)
    total_success = sum(item["success_count"] for item in round_results)
    total_failure = sum(item["failure_count"] for item in round_results)
    avg_latency_values = [item["avg_latency_ms"] for item in round_results if item["avg_latency_ms"] > 0]
    throughput = total_records / total_elapsed if total_elapsed > 0 else 0.0
    status_counter: Counter[str] = Counter()
    error_counter: Counter[str] = Counter()
    backoff_error_counter: Counter[str] = Counter()

    for item in round_results:
        status_counter.update(item["status_code_counts"])
        error_counter.update(item["error_type_counts"])
        backoff_error_counter.update(item["backoff"]["error_type_counts"])

    return {
        "label": label,
        "sources": selected_sources,
        "qps": qps,
        "rounds": rounds,
        "addresses_per_round": limit,
        "estimated_total_requests": rounds * limit * len(selected_sources),
        "max_workers": max_workers,
        "initial_limit": initial_limit,
        "elapsed_sec": round(total_elapsed, 3),
        "total_records": total_records,
        "success_count": total_success,
        "failure_count": total_failure,
        "success_rate_pct": round((total_success / total_records) * 100, 2) if total_records else 0.0,
        "avg_latency_ms": round(sum(avg_latency_values) / len(avg_latency_values), 2) if avg_latency_values else 0.0,
        "throughput_rps": round(throughput, 3),
        "status_code_counts": dict(sorted(status_counter.items())),
        "error_type_counts": dict(sorted(error_counter.items())),
        "http_429_count": sum(item["http_429_count"] for item in round_results),
        "http_403_count": sum(item["http_403_count"] for item in round_results),
        "timeout_count": sum(item["timeout_count"] for item in round_results),
        "conn_error_count": sum(item["conn_error_count"] for item in round_results),
        "backoff_trigger_count": sum(item["backoff"]["trigger_count"] for item in round_results),
        "backoff_error_counts": dict(sorted(backoff_error_counter.items())),
        "resource_usage": resource_stats,
        "round_results": round_results,
    }


def _print_report(results: list[dict[str, Any]]) -> None:
    print()
    print("Stress Benchmark Results")
    print("-" * 168)
    print(
        f"{'Label':<24}"
        f"{'Workers':>8}"
        f"{'Init':>8}"
        f"{'Rounds':>8}"
        f"{'Records':>10}"
        f"{'Success':>10}"
        f"{'Fail':>8}"
        f"{'Time(s)':>10}"
        f"{'Avg Lat(ms)':>14}"
        f"{'Req/s':>10}"
        f"{'429':>8}"
        f"{'Timeout':>10}"
        f"{'Backoff':>10}"
        f"{'Avg CPU%':>12}"
        f"{'Peak Mem(MB)':>16}"
    )
    print("-" * 168)
    for item in results:
        usage = item["resource_usage"]
        avg_cpu = usage["avg_cpu_pct"] if usage["avg_cpu_pct"] is not None else "n/a"
        peak_mem = usage["peak_memory_mb"] if usage["peak_memory_mb"] is not None else "n/a"
        print(
            f"{item['label']:<24}"
            f"{item['max_workers']:>8}"
            f"{item['initial_limit']:>8}"
            f"{item['rounds']:>8}"
            f"{item['total_records']:>10}"
            f"{item['success_count']:>10}"
            f"{item['failure_count']:>8}"
            f"{item['elapsed_sec']:>10.3f}"
            f"{item['avg_latency_ms']:>14.2f}"
            f"{item['throughput_rps']:>10.3f}"
            f"{item['http_429_count']:>8}"
            f"{item['timeout_count']:>10}"
            f"{item['backoff_trigger_count']:>10}"
            f"{str(avg_cpu):>12}"
            f"{str(peak_mem):>16}"
        )
    print("-" * 168)
    print()
    print("Detailed error counters by configuration:")
    for item in results:
        print(
            f"- {item['label']}: "
            f"status_codes={item['status_code_counts']}, "
            f"errors={item['error_type_counts']}, "
            f"backoff_errors={item['backoff_error_counts']}"
        )
    print()
    if psutil is None:
        print("psutil is not installed, so CPU and memory metrics were skipped.")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a larger stress benchmark for clearer single-thread vs multi-thread comparisons."
    )
    parser.add_argument("--addresses", default=DEFAULT_ADDRESS_LIST_PATH, help="Path to the address list file.")
    parser.add_argument("--curl-config", default=DEFAULT_CURL_CONFIG_PATH, help="Path to the curl config file.")
    parser.add_argument("--output-dir", default="testdata/stress_benchmarks", help="Directory for round result files.")
    parser.add_argument(
        "--save-json",
        default="testdata/stress_benchmarks/stress_benchmark_summary.json",
        help="Path to save aggregated stress benchmark results as JSON.",
    )
    parser.add_argument(
        "--qps",
        type=float,
        default=0.0,
        help="Global QPS limit used during stress benchmarking. Use 0 to disable rate limiting.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of tasks used in each round. If the address list is shorter, addresses are repeated automatically.",
    )
    parser.add_argument("--rounds", type=int, default=1, help="How many times to repeat the same workload.")
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["web2"],
        help="Sources to benchmark, for example: web1 web2",
    )
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=0.2,
        help="Resource usage sample interval in seconds.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    results: list[dict[str, Any]] = []

    for config in _build_default_configs():
        benchmark_dir = output_dir / config["label"]
        benchmark_result = _run_stress_benchmark(
            label=config["label"],
            rounds=args.rounds,
            addresses_path=args.addresses,
            curl_config_path=args.curl_config,
            output_dir=benchmark_dir,
            qps=args.qps,
            max_workers=config["max_workers"],
            initial_limit=config["initial_limit"],
            limit=args.limit,
            selected_sources=args.sources,
            sample_interval=args.sample_interval,
        )
        results.append(benchmark_result)

    _print_report(results)

    save_path = Path(args.save_json)
    if save_path.parent and str(save_path.parent) not in {".", ""}:
        save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Saved stress benchmark summary to: {save_path}")


if __name__ == "__main__":
    main()
