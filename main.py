from __future__ import annotations

import argparse
import threading
import time
import uuid

from src.backoff import BackoffStrategy
from src.controller import ThreadPoolController
from src.factory import ScraperFactory
from src.metrics import MetricsCollector
from src.rate_limiter import RateLimiter
from src.smart_controller import SmartController
from src.storage import JsonlStorage
from src.strategies import ChangeProxyStrategy, IncreaseConcurrencyStrategy, ReduceConcurrencyStrategy
from src.models import Task


CURL_CONFIG_PATH = "curl_config.txt"

def _load_curl_config(path: str) -> str:
    """Load the raw cURL command template from a config file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


ADDRESS_LIST_PATH = "testlist.txt"


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


def _build_tasks() -> list[Task]:
    tasks: list[Task] = []
    addresses = _load_addresses(ADDRESS_LIST_PATH, limit=100)

    # Web1 (gmgn) - based on test.py, minimal headers + body
    gmgn_url = "https://gmgn.ai/api/v1/mutil_window_token_info"
    raw_curl = _load_curl_config(CURL_CONFIG_PATH)
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
                        "chain": "bsc",
                        "addresses": [addr],
                    },
                )
            )

    # Web2 (dexscreener) - based on test2.py
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


def run_demo() -> None:
    metrics = MetricsCollector()
    rate_limiter = RateLimiter(qps=2.0)
    backoff = BackoffStrategy()
    factory = ScraperFactory(
        metrics=metrics,
        rate_limiter=rate_limiter,
        backoff=backoff,
    )
    storage = JsonlStorage("results.jsonl")

    controller = ThreadPoolController(max_workers=8, initial_limit=3)
    controller.start()

    strategies = [
        ReduceConcurrencyStrategy(),
        ChangeProxyStrategy(),
        IncreaseConcurrencyStrategy(),
    ]
    smart = SmartController(metrics, controller, strategies, eval_interval_secs=5, window_secs=15)
    smart_thread = threading.Thread(target=smart.start, daemon=True)
    smart_thread.start()

    tasks = _build_tasks()
    futures = []
    for task in tasks:
        scraper = factory.create_scraper(task)
        futures.append(controller.submit(scraper.run, task))

    for fut in futures:
        result = fut.result()
        storage.write(result)
        print(
            f"task={result.task_id} source={result.source_id} success={result.success} "
            f"status={result.status_code} latency_ms={result.latency_ms} error={result.error_type}"
        )

    smart.stop()
    controller.stop(wait=True)
    storage.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-demo", action="store_true", help="Run a minimal end-to-end demo")
    args = parser.parse_args()

    if args.run_demo:
        run_demo()
        return

    print("Nothing to do. Use --run-demo to run the demo.")


if __name__ == "__main__":
    main()
