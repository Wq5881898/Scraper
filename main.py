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


RAW_CURL = r"""curl 'https://gmgn.ai/api/v1/mutil_window_token_info?device_id=2f7a7a39-6426-4218-b88e-9e3db3545b81&fp_did=058a0c07a7afecfc9ddc2d333226a0ff&client_id=gmgn_web_20260218-11075-5093a13&from_app=gmgn&app_ver=20260218-11075-5093a13&tz_name=America%2FDenver&tz_offset=-25200&app_lang=zh-CN&os=web&worker=0' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'accept-language: zh-CN,zh;q=0.9,en;q=0.8' \
  -H 'baggage: sentry-environment=production,sentry-release=20260218-11075-5093a13,sentry-public_key=93c25bab7246077dc3eb85b59d6e7d40,sentry-trace_id=72e4f1f9041340e29c29f7126acc38b9,sentry-org_id=4505147559706624,sentry-transaction=%2F%5Bchain%5D%2Ftoken%2F%5Btoken%5D,sentry-sampled=false,sentry-sample_rand=0.7617325227269099,sentry-sample_rate=0.01' \
  -H 'content-type: application/json' \
  -b '_ga=GA1.1.1233147309.1769553624; __cf_bm=93fcEaVKu0mW51iu.8NikuZbvsbpo12Ljo3l2Zaf5tc-1771479541-1.0.1.1-qYFbwR3ogpM79LBG6tgJlew4aCOG5uLTBZQXRJR20RKNh6kHZgTgiEOE4wCbXVQ8QcXeUyTiDT0xekbjqBYWtavcDS2AVCt4ANXx1VU6z2s; _ga_0XM0LYXGC8=GS2.1.s1771479754$o13$g0$t1771479754$j60$l0$h0' \
  -H 'origin: https://gmgn.ai' \
  -H 'priority: u=1, i' \
  -H 'referer: https://gmgn.ai/bsc/token/0x783c3f003f172c6ac5ac700218a357d2d66ee2a2' \
  -H 'sec-ch-ua: "Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "Windows"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-site: same-origin' \
  -H 'sentry-trace: 72e4f1f9041340e29c29f7126acc38b9-aadf8a64f049464b-0' \
  -H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36' \
  --data-raw '{"chain":"bsc","addresses":["0x783c3f003f172c6ac5ac700218a357d2d66ee2a2"]}'
"""
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
    if RAW_CURL.strip():
        for addr in addresses:
            tasks.append(
                Task(
                    task_id=str(uuid.uuid4()),
                    source_id="web1",
                    url=gmgn_url,
                    params={},
                    meta={
                        "raw_curl": RAW_CURL,
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
