from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any


def _to_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return default


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _extract_success(row: dict[str, Any]) -> bool:
    if "success" in row:
        return _to_bool(row["success"])
    if "status" in row:
        return _to_bool(row["status"])

    status_code = _to_float(row.get("status_code"))
    if status_code is None:
        return False
    return 200 <= status_code < 400


def _extract_latency_ms(row: dict[str, Any]) -> float:
    latency = _to_float(row.get("latency_ms"))
    if latency is None:
        latency = _to_float(row.get("latency"))
    return latency if latency is not None else 0.0


def _compute_change_pct(current_price: float | None, historical_price: float | None) -> float | None:
    if current_price is None or historical_price is None or historical_price == 0:
        return None
    return (current_price - historical_price) / historical_price * 100.0


def _compute_historical_price(current_price: float | None, change_pct: float | None) -> float | None:
    if current_price is None or change_pct is None:
        return None
    divisor = 1.0 + (change_pct / 100.0)
    if divisor == 0:
        return None
    return current_price / divisor


def _to_iso_utc_from_seconds(value: Any) -> str | None:
    numeric = _to_float(value)
    if numeric is None or numeric <= 0:
        return None
    return datetime.fromtimestamp(numeric, tz=timezone.utc).isoformat()


def normalize_result_record(row: dict[str, Any]) -> dict[str, Any]:
    source_id = str(row.get("source_id", "unknown"))
    normalized: dict[str, Any] = {
        "timestamp": _to_float(row.get("timestamp")),
        "task_id": row.get("task_id"),
        "source_id": source_id,
        "url": row.get("url"),
        "success": _extract_success(row),
        "status_code": row.get("status_code"),
        "latency_ms": _extract_latency_ms(row),
        "error_type": row.get("error_type"),
        "token_name": None,
        "symbol": None,
        "price_usd": None,
        "liquidity_usd": None,
        "market_cap": None,
        "fdv": None,
        "volume_h24": None,
        "holder_count": None,
        "circulating_supply": None,
        "total_supply": None,
        "max_supply": None,
        "price_1m": None,
        "price_5m": None,
        "price_1h": None,
        "price_6h": None,
        "price_24h": None,
        "price_change_m1_pct": None,
        "price_change_m5_pct": None,
        "price_change_h1_pct": None,
        "price_change_h6_pct": None,
        "price_change_h24_pct": None,
        "created_at_utc": None,
    }

    payload = row.get("parsed_data")

    if source_id == "web1":
        token = payload[0] if isinstance(payload, list) and payload else payload
        if not isinstance(token, dict):
            return normalized

        price_block = token.get("price") if isinstance(token.get("price"), dict) else {}
        current_price = _to_float(price_block.get("price"))
        circulating_supply = _to_float(token.get("circulating_supply"))
        total_supply = _to_float(token.get("total_supply"))
        max_supply = _to_float(token.get("max_supply"))
        fdv_supply = max_supply if max_supply is not None else total_supply

        price_1m = _to_float(price_block.get("price_1m"))
        price_5m = _to_float(price_block.get("price_5m"))
        price_1h = _to_float(price_block.get("price_1h"))
        price_6h = _to_float(price_block.get("price_6h"))
        price_24h = _to_float(price_block.get("price_24h"))

        normalized.update(
            {
                "token_name": token.get("name") or token.get("token_name"),
                "symbol": token.get("symbol") or token.get("token_symbol"),
                "price_usd": current_price,
                "liquidity_usd": _to_float(token.get("liquidity")),
                "market_cap": current_price * circulating_supply if current_price is not None and circulating_supply is not None else None,
                "fdv": current_price * fdv_supply if current_price is not None and fdv_supply is not None else None,
                "volume_h24": _to_float(price_block.get("volume_24h")),
                "holder_count": _to_float(token.get("holder_count")),
                "circulating_supply": circulating_supply,
                "total_supply": total_supply,
                "max_supply": max_supply,
                "price_1m": price_1m,
                "price_5m": price_5m,
                "price_1h": price_1h,
                "price_6h": price_6h,
                "price_24h": price_24h,
                "price_change_m1_pct": _compute_change_pct(current_price, price_1m),
                "price_change_m5_pct": _compute_change_pct(current_price, price_5m),
                "price_change_h1_pct": _compute_change_pct(current_price, price_1h),
                "price_change_h6_pct": _compute_change_pct(current_price, price_6h),
                "price_change_h24_pct": _compute_change_pct(current_price, price_24h),
                "created_at_utc": _to_iso_utc_from_seconds(token.get("creation_timestamp")),
            }
        )
        return normalized

    if source_id == "web2" and isinstance(payload, dict):
        current_price = _to_float(payload.get("price_usd"))
        market_cap = _to_float(payload.get("market_cap"))
        fdv = _to_float(payload.get("fdv"))
        price_change = payload.get("price_change") if isinstance(payload.get("price_change"), dict) else {}

        change_m5 = _to_float(price_change.get("m5"))
        change_h1 = _to_float(price_change.get("h1"))
        change_h6 = _to_float(price_change.get("h6"))
        change_h24 = _to_float(price_change.get("h24"))

        circulating_supply = market_cap / current_price if market_cap is not None and current_price not in (None, 0) else None
        diluted_supply = fdv / current_price if fdv is not None and current_price not in (None, 0) else None

        normalized.update(
            {
                "token_name": payload.get("token_name") or payload.get("name"),
                "symbol": payload.get("symbol"),
                "price_usd": current_price,
                "liquidity_usd": _to_float(payload.get("liquidity_usd")),
                "market_cap": market_cap,
                "fdv": fdv,
                "volume_h24": _to_float(payload.get("volume_h24")),
                "holder_count": _to_float(payload.get("holder_count")),
                "circulating_supply": circulating_supply,
                "total_supply": diluted_supply,
                "max_supply": diluted_supply,
                "price_1m": None,
                "price_5m": _compute_historical_price(current_price, change_m5),
                "price_1h": _compute_historical_price(current_price, change_h1),
                "price_6h": _compute_historical_price(current_price, change_h6),
                "price_24h": _compute_historical_price(current_price, change_h24),
                "price_change_m1_pct": None,
                "price_change_m5_pct": change_m5,
                "price_change_h1_pct": change_h1,
                "price_change_h6_pct": change_h6,
                "price_change_h24_pct": change_h24,
                "created_at_utc": payload.get("created_at_utc"),
            }
        )
        return normalized

    return normalized


def iter_results(path: str) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    invalid_lines = 0

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                invalid_lines += 1
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
            else:
                invalid_lines += 1

    return rows, invalid_lines


def summarize_results(path: str) -> dict[str, Any]:
    rows, invalid_lines = iter_results(path)
    if not rows:
        return {
            "path": path,
            "total_records": 0,
            "invalid_lines": invalid_lines,
            "overall": {
                "successes": 0,
                "failures": 0,
                "success_rate_pct": 0.0,
                "avg_latency_ms": 0.0,
                "min_latency_ms": 0.0,
                "max_latency_ms": 0.0,
            },
            "by_source": [],
        }

    by_source: dict[str, dict[str, Any]] = {}
    total_success = 0
    total_fail = 0
    all_latencies: list[float] = []

    for row in rows:
        source_id = str(row.get("source_id", "unknown"))
        success = _extract_success(row)
        latency = _extract_latency_ms(row)

        all_latencies.append(latency)
        if success:
            total_success += 1
        else:
            total_fail += 1

        if source_id not in by_source:
            by_source[source_id] = {
                "source_id": source_id,
                "total": 0,
                "successes": 0,
                "failures": 0,
                "avg_latency_ms": 0.0,
                "min_latency_ms": 0.0,
                "max_latency_ms": 0.0,
            }

        current = by_source[source_id]
        current["total"] += 1
        if success:
            current["successes"] += 1
        else:
            current["failures"] += 1

        if current["total"] == 1:
            current["min_latency_ms"] = latency
            current["max_latency_ms"] = latency
            current["avg_latency_ms"] = latency
        else:
            current["min_latency_ms"] = min(current["min_latency_ms"], latency)
            current["max_latency_ms"] = max(current["max_latency_ms"], latency)
            previous_avg = current["avg_latency_ms"]
            current["avg_latency_ms"] = previous_avg + (latency - previous_avg) / current["total"]

    total = len(rows)
    overall_avg = sum(all_latencies) / total if total else 0.0
    by_source_list = sorted(by_source.values(), key=lambda item: item["source_id"])
    for item in by_source_list:
        item["success_rate_pct"] = (item["successes"] / item["total"] * 100.0) if item["total"] else 0.0

    return {
        "path": path,
        "total_records": total,
        "invalid_lines": invalid_lines,
        "overall": {
            "successes": total_success,
            "failures": total_fail,
            "success_rate_pct": (total_success / total * 100.0) if total else 0.0,
            "avg_latency_ms": overall_avg,
            "min_latency_ms": min(all_latencies) if all_latencies else 0.0,
            "max_latency_ms": max(all_latencies) if all_latencies else 0.0,
        },
        "by_source": by_source_list,
    }


def read_recent_records(path: str, limit: int = 20) -> dict[str, Any]:
    rows, invalid_lines = iter_results(path)
    valid_limit = max(1, min(limit, 500))
    return {
        "path": path,
        "limit": valid_limit,
        "invalid_lines": invalid_lines,
        "records": rows[-valid_limit:],
    }


def iter_normalized_results(path: str) -> tuple[list[dict[str, Any]], int]:
    rows, invalid_lines = iter_results(path)
    return [normalize_result_record(row) for row in rows], invalid_lines


def normalized_output_path(path: str) -> str:
    src = Path(path)
    if src.suffix:
        return str(src.with_name(f"{src.stem}.normalized{src.suffix}"))
    return str(src.with_name(f"{src.name}.normalized.jsonl"))


def write_normalized_results(path: str, output_path: str | None = None) -> dict[str, Any]:
    normalized_rows, invalid_lines = iter_normalized_results(path)
    target_path = output_path or normalized_output_path(path)
    target = Path(target_path)
    if target.parent and str(target.parent) not in {".", ""}:
        target.parent.mkdir(parents=True, exist_ok=True)

    with open(target, "w", encoding="utf-8") as f:
        for row in normalized_rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    return {
        "path": path,
        "output_path": str(target),
        "invalid_lines": invalid_lines,
        "total_records": len(normalized_rows),
    }
