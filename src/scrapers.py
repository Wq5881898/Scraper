from __future__ import annotations

import datetime as _dt
import json as _json
import shlex as _shlex
import time as _time
from typing import Any, Optional
from urllib.parse import parse_qsl as _parse_qsl, urlsplit as _urlsplit, urlunsplit as _urlunsplit

from curl_cffi import requests as curl_requests
import requests

from .base import BaseScraper
from .backoff import BackoffStrategy
from .models import Task
from .rate_limiter import RateLimiter


class Web1Scraper(BaseScraper):
    def __init__(
        self,
        rate_limiter: RateLimiter,
        backoff: BackoffStrategy,
        max_retries: int = 3,
        timeout: int = 20,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._rate_limiter = rate_limiter
        self._backoff = backoff
        self._max_retries = max_retries
        self._timeout = timeout

    def fetch(self, task: Task) -> Any:
        raw_curl = task.meta.get("raw_curl")
        if raw_curl:
            fields = _parse_curl_to_fields(raw_curl)
            method = fields["METHOD"]
            api_url = fields["API_URL"]
            params = fields["PARAMS"]
            headers = fields["HEADERS"]
            cookies = fields["COOKIES"] or None
            json_data = fields["JSON_DATA"]
            raw_body = fields["RAW_BODY"] or None
            if isinstance(json_data, dict):
                if "chain" in task.meta:
                    json_data["chain"] = task.meta["chain"]
                if "addresses" in task.meta:
                    json_data["addresses"] = task.meta["addresses"]
            token = (task.meta.get("addresses") or [None])[0]
        else:
            method = task.meta.get("method", "GET")
            api_url = task.url
            params = task.params or None
            headers = task.meta.get("headers")
            cookies = task.meta.get("cookies")
            json_data = task.meta.get("json")
            raw_body = task.meta.get("data")
            token = (task.meta.get("addresses") or [None])[0]

        attempt = 0
        while True:
            attempt += 1
            self._rate_limiter.acquire()
            session = curl_requests.Session()
            try:
                response = session.request(
                    method=method,
                    url=api_url,
                    params=params or None,
                    json=json_data,
                    data=None if json_data is not None else raw_body,
                    headers=headers,
                    cookies=cookies,
                    impersonate="chrome120",
                    timeout=self._timeout,
                )
                response._token = token
                return response
            except Exception as exc:  # noqa: BLE001
                if attempt >= self._max_retries:
                    raise
                sleep_s = self._backoff.get_sleep(attempt, type(exc).__name__)
                _time.sleep(sleep_s)

    def parse(self, response: Any) -> Any:
        token = getattr(response, "_token", None)
        status_code = getattr(response, "status_code", None)
        try:
            payload = response.json()
        except Exception:  # noqa: BLE001
            raw_text = getattr(response, "text", "")
            return {
                "token": token,
                "error": "invalid_json",
                "status_code": status_code,
                "raw_text": raw_text[:1000],
            }

        if status_code not in (200, 201):
            error_msg = None
            if isinstance(payload, dict):
                error_msg = payload.get("error") or payload.get("message")
            return {
                "token": token,
                "error": error_msg or f"http_{status_code}",
                "status_code": status_code,
                "raw": payload,
            }

        if isinstance(payload, dict):
            data = payload.get("data") or payload.get("result")
            if not data:
                return {
                    "token": token,
                    "error": f"can not find {token}" if token else "can not find token",
                    "status_code": status_code,
                }
            return data
        return payload


class Web2Scraper(BaseScraper):
    def __init__(
        self,
        rate_limiter: RateLimiter,
        backoff: BackoffStrategy,
        max_retries: int = 3,
        timeout: int = 20,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._rate_limiter = rate_limiter
        self._backoff = backoff
        self._max_retries = max_retries
        self._timeout = timeout

    def fetch(self, task: Task) -> Any:
        attempt = 0
        while True:
            attempt += 1
            self._rate_limiter.acquire()
            start = _time.time()
            try:
                resp = requests.get(
                    task.url,
                    params=task.params or None,
                    headers=task.meta.get("headers"),
                    timeout=self._timeout,
                )
                resp.latency_ms = int((_time.time() - start) * 1000)
                resp._query = (task.params or {}).get("q")  # attach query for parse
                return resp
            except Exception as exc:  # noqa: BLE001
                if attempt >= self._max_retries:
                    raise
                sleep_s = self._backoff.get_sleep(attempt, type(exc).__name__)
                _time.sleep(sleep_s)

    def parse(self, response: Any) -> Any:
        try:
            data = response.json()
        except Exception:  # noqa: BLE001
            return {"raw_text": getattr(response, "text", "")}

        pairs = data.get("pairs") if isinstance(data, dict) else None
        if not pairs:
            error_msg = None
            if isinstance(data, dict):
                error_msg = data.get("error") or data.get("message")
            token = getattr(response, "_query", None)
            not_found_msg = f"can not find {token}" if token else "can not find token"
            return {
                "pairs": [],
                "error": error_msg or not_found_msg,
                "status_code": getattr(response, "status_code", None),
            }

        pair = pairs[0]
        pair_created_ms = pair.get("pairCreatedAt", 0) or 0
        created_at = _dt.datetime.fromtimestamp(pair_created_ms / 1000, tz=_dt.timezone.utc)

        return {
            "token_name": pair.get("baseToken", {}).get("name"),
            "chain_id": pair.get("chainId"),
            "dex_id": pair.get("dexId"),
            "price_usd": pair.get("priceUsd"),
            "liquidity_usd": (pair.get("liquidity") or {}).get("usd"),
            "market_cap": pair.get("marketCap"),
            "fdv": pair.get("fdv"),
            "volume_h24": (pair.get("volume") or {}).get("h24"),
            "price_change": pair.get("priceChange", {}),
            "created_at_utc": created_at.isoformat(),
        }


def _parse_cookie_str(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for pair in raw.split(";"):
        part = pair.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        cookies[k.strip()] = v.strip()
    return cookies


def _parse_curl_to_fields(curl_cmd: str) -> dict:
    tokens = _shlex.split(curl_cmd, posix=True)
    if not tokens or tokens[0] != "curl":
        raise ValueError("RAW_CURL must start with 'curl'.")

    method = "GET"
    raw_url = ""
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}
    body = ""

    i = 1
    while i < len(tokens):
        t = tokens[i]
        if t in ("-X", "--request"):
            method = tokens[i + 1].upper()
            i += 2
            continue
        if t in ("-H", "--header"):
            hv = tokens[i + 1]
            if ":" in hv:
                k, v = hv.split(":", 1)
                if k.strip().lower() != "cookie":
                    headers[k.strip()] = v.strip()
                else:
                    cookies.update(_parse_cookie_str(v.strip()))
            i += 2
            continue
        if t in ("-b", "--cookie"):
            cookies.update(_parse_cookie_str(tokens[i + 1].strip()))
            i += 2
            continue
        if t in ("--data", "--data-raw", "--data-binary", "--data-urlencode", "-d"):
            body = tokens[i + 1]
            if method == "GET":
                method = "POST"
            i += 2
            continue
        if t == "--url":
            raw_url = tokens[i + 1]
            i += 2
            continue
        if t.startswith("http://") or t.startswith("https://"):
            raw_url = t
            i += 1
            continue
        i += 1

    if not raw_url:
        raise ValueError("No URL found in RAW_CURL.")

    u = _urlsplit(raw_url)
    api_url = _urlunsplit((u.scheme, u.netloc, u.path, "", ""))
    params = dict(_parse_qsl(u.query, keep_blank_values=True))

    json_data = None
    if body:
        try:
            json_data = _json.loads(body)
        except _json.JSONDecodeError:
            json_data = None

    return {
        "METHOD": method,
        "API_URL": api_url,
        "PARAMS": params,
        "HEADERS": headers,
        "COOKIES": cookies,
        "JSON_DATA": json_data,
        "RAW_BODY": body,
    }
