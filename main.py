from __future__ import annotations

import argparse
import threading
import time
import uuid
from typing import Optional

from src.backoff import BackoffStrategy
from src.controller import ThreadPoolController
from src.factory import ScraperFactory
from src.metrics import MetricsCollector
from src.rate_limiter import RateLimiter
from src.smart_controller import SmartController
from src.storage import JsonlStorage
from src.strategies import ChangeProxyStrategy, IncreaseConcurrencyStrategy, ReduceConcurrencyStrategy
from src.models import Task

from src.scrapers import _parse_curl_to_fields


DEFAULT_CURL_CONFIG_PATH = "curl_config.txt"
DEFAULT_ADDRESS_LIST_PATH = "testlist.txt"


def _load_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def _load_addresses(path: str, limit: int = 100) -> list[str]:
    addresses: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            addr = line.strip()
            if not addr:
                continue
            addresses.append(addr)
            if len(addresses) >= limit:
                break
    if not addresses:
        raise ValueError(f"No addresses found in {path}")
    return addresses


def _build_tasks(address_path: str, curl_config_path: str, limit: int) -> list[Task]:
    tasks: list[Task] = []
    addresses = _load_addresses(address_path, limit=limit)

    # Web1 (gmgn)
    gmgn_url = "https://gmgn.ai/api/v1/mutil_window_token_info"
    raw_curl = _load_text(curl_config_path)

    curl_fields = None
    if raw_curl:
        # Parse once; avoid parsing for every task
        try:
            curl_fields = _parse_curl_to_fields(raw_curl)
        except Exception:
            curl_fields = None

    if raw_curl:
        for addr in addresses:
            tasks.append(
                Task(
                    task_id=str(uuid.uuid4()),
                    source_id="web1",
                    url=gmgn_url,
                    params={},
                    meta={
                        "raw_curl": raw_curl,
                        "curl_fields": curl_fields,  # pre-parsed, optional
                        "chain": "bsc",
                        "addresses": [addr],
                    },
                )
            )

    # Web2 (dexscreener)
    dexscreener_url = "https://api.dexscreener.com/latest/dex/search/"
    for addr in addresses:
        tasks.append(
            Task(
                task_id=str(uuid.uuid4()),
                source_id="web2",
                url=dexscreener_url,
                params={"q": addr},
                meta={},
            )
        )

    return tasks


def run_demo(
    address_path: str,
    curl_config_path: str,
    results_path: str,
    address_limit: int,
    qps: float,
    max_workers: int,
    initial_limit: int,
    eval_interval: int,
    window_secs: int,
) -> None:
    metrics = MetricsCollector()
    rate_limiter = RateLimiter(qps=qps)
    backoff = BackoffStrategy()
    factory = ScraperFactory(
        metrics=metrics,
        rate_limiter=rate_limiter,
        backoff=backoff,
        cache_web1=False,   # safer (web1 might have session/thread concerns)
        cache_web2=True,    # ok to share
    )
    storage = JsonlStorage(results_path)

    controller = ThreadPoolController(max_workers=max_workers, initial_limit=initial_limit)
    controller.start()

    strategies = [
        ReduceConcurrencyStrategy(),
        ChangeProxyStrategy(),
        IncreaseConcurrencyStrategy(),
    ]
    smart = SmartController(metrics, controller, strategies, eval_interval_secs=eval_interval, window_secs=window_secs)
    smart_thread = threading.Thread(target=smart.start, daemon=True)
    smart_thread.start()

    tasks = _build_tasks(address_path, curl_config_path, address_limit)

    futures = []
    for task in tasks:
        scraper = factory.create_scraper(task)
        futures.append(controller.submit(scraper.run, task))

    # Consume results as they complete (simple join)
    ok = 0
    fail = 0
    for fut in futures:
        result = fut.result()
        storage.write(result)
        if result.success:
            ok += 1
        else:
            fail += 1

        print(
            f"task={result.task_id} source={result.source_id} success={result.success} "
            f"status={result.status_code} latency_ms={result.latency_ms} error={result.error_type}"
        )

    smart.stop()
    controller.stop(wait=True)
    storage.close()

    print(f"\nDONE: success={ok} fail={fail} total={ok + fail}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-demo", action="store_true", help="Run a minimal end-to-end demo")

    parser.add_argument("--addresses", default=DEFAULT_ADDRESS_LIST_PATH, help="Path to address list (testlist.txt)")
    parser.add_argument("--curl-config", default=DEFAULT_CURL_CONFIG_PATH, help="Path to curl config (curl_config.txt)")
    parser.add_argument("--results", default="results.jsonl", help="Output JSONL file path")

    parser.add_argument("--limit", type=int, default=100, help="Max number of addresses to load")
    parser.add_argument("--qps", type=float, default=2.0, help="Global QPS rate limiter")
    parser.add_argument("--max-workers", type=int, default=8, help="ThreadPoolExecutor max workers")
    parser.add_argument("--initial-limit", type=int, default=3, help="Initial concurrency limit")

    parser.add_argument("--eval-interval", type=int, default=5, help="SmartController eval interval seconds")
    parser.add_argument("--window-secs", type=int, default=15, help="Metrics sliding window seconds")

    args = parser.parse_args()

    if args.run_demo:
        run_demo(
            address_path=args.addresses,
            curl_config_path=args.curl_config,
            results_path=args.results,
            address_limit=args.limit,
            qps=args.qps,
            max_workers=args.max_workers,
            initial_limit=args.initial_limit,
            eval_interval=args.eval_interval,
            window_secs=args.window_secs,
        )
        return

    print("Nothing to do. Use --run-demo to run the demo.")


if __name__ == "__main__":
    main()