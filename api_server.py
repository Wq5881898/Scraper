from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from flasgger import Swagger
from flask import Flask, jsonify, request

from main import (
    DEFAULT_ADDRESS_LIST_PATH,
    DEFAULT_CURL_CONFIG_PATH,
    DEFAULT_RESULTS_PATH,
    run_demo,
)
from src.results_reader import (
    iter_normalized_results,
    iter_results,
    normalized_output_path,
    read_recent_records,
    summarize_results,
    write_normalized_results,
)


def create_app(default_results_path: str = DEFAULT_RESULTS_PATH) -> Flask:
    app = Flask(__name__)
    app.config["SWAGGER"] = {
        "title": "Scraper API",
        "uiversion": 3,
    }

    template: dict[str, Any] = {
        "swagger": "2.0",
        "info": {
            "title": "Scraper API",
            "description": "Swagger 2 endpoints for scraper health, JSONL analytics, and run-demo integration.",
            "version": "1.0.0",
        },
        "basePath": "/",
        "schemes": ["http"],
    }
    Swagger(app, template=template)

    def _resolve_path() -> str:
        path = request.args.get("path", "").strip()
        if not path:
            path = default_results_path
        return path

    def _json_error(message: str, status_code: int = 400):
        # Added by Qi: build a consistent JSON error response for the new Run Page API.
        response = jsonify({"status": "error", "message": message})
        response.status_code = status_code
        return response

    def _to_positive_float(value: Any, field_name: str) -> float:
        # Added by Qi: validate float inputs such as qps before calling run_demo().
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be a valid number.") from exc
        if parsed <= 0:
            raise ValueError(f"{field_name} must be greater than 0.")
        return parsed

    def _to_positive_int(value: Any, field_name: str) -> int:
        # Added by Qi: validate integer inputs such as worker counts and limits for the Run Page API.
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be a valid integer.") from exc
        if parsed < 1:
            raise ValueError(f"{field_name} must be at least 1.")
        return parsed

    def _normalize_source_selection(value: Any) -> list[str]:
        # Added by Qi: validate selectable scraper sources so the Run Page can scale to web1, web2, web3, and beyond.
        allowed_sources = {"web1", "web2"}
        if value is None:
            return ["web1", "web2"]
        if not isinstance(value, list):
            raise ValueError("selected_sources must be a list.")

        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if not cleaned:
            raise ValueError("At least one source must be selected.")

        invalid_sources = [item for item in cleaned if item not in allowed_sources]
        if invalid_sources:
            raise ValueError(f"Unknown source selection: {', '.join(invalid_sources)}")
        return cleaned

    def _normalize_run_payload(payload: dict[str, Any]) -> dict[str, Any]:
        # Added by Qi: normalize and validate frontend Run Page payload into the exact run_demo() arguments.
        addresses = str(payload.get("addresses", DEFAULT_ADDRESS_LIST_PATH)).strip()
        curl_config = str(payload.get("curl_config", DEFAULT_CURL_CONFIG_PATH)).strip()
        results = str(payload.get("results", default_results_path)).strip()

        if not addresses:
            raise ValueError("addresses is required.")
        if not curl_config:
            raise ValueError("curl_config is required.")
        if not results:
            raise ValueError("results is required.")

        return {
            "addresses": addresses,
            "curl_config": curl_config,
            "results": results,
            "qps": _to_positive_float(payload.get("qps", 2.0), "qps"),
            "max_workers": _to_positive_int(payload.get("max_workers", 8), "max_workers"),
            "initial_limit": _to_positive_int(payload.get("initial_limit", 3), "initial_limit"),
            "limit": _to_positive_int(payload.get("limit", 100), "limit"),
            "selected_sources": _normalize_source_selection(payload.get("selected_sources")),
        }

    @app.after_request
    def add_cors_headers(response):
        # Added by Qi: allow the React dashboard to call the Flask API from a separate dev server.
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response

    @app.get("/health")
    def health() -> Any:
        """
        Service health check.
        ---
        tags:
          - System
        responses:
          200:
            description: Service is healthy.
            schema:
              type: object
              properties:
                status:
                  type: string
                  example: ok
        """
        return jsonify({"status": "ok"})

    @app.get("/summary")
    def summary() -> Any:
        """
        Summarize a scraper JSONL file by source and latency.
        ---
        tags:
          - Results
        parameters:
          - name: path
            in: query
            required: false
            type: string
            description: JSONL file path. Defaults to testdata/results.jsonl.
        responses:
          200:
            description: Summary computed.
          404:
            description: File does not exist.
        """
        path = _resolve_path()
        if not os.path.exists(path):
            return jsonify({"error": f"File not found: {path}"}), 404
        return jsonify(summarize_results(path))

    @app.get("/records")
    def records() -> Any:
        """
        Return latest records from a scraper JSONL file.
        ---
        tags:
          - Results
        parameters:
          - name: path
            in: query
            required: false
            type: string
            description: JSONL file path. Defaults to testdata/results.jsonl.
          - name: limit
            in: query
            required: false
            type: integer
            default: 20
            minimum: 1
            maximum: 500
        responses:
          200:
            description: Recent records returned.
          404:
            description: File does not exist.
        """
        path = _resolve_path()
        if not os.path.exists(path):
            return jsonify({"error": f"File not found: {path}"}), 404

        raw_limit = request.args.get("limit", "20")
        try:
            limit = int(raw_limit)
        except ValueError:
            limit = 20

        return jsonify(read_recent_records(path, limit=limit))

    @app.get("/normalized-records")
    def normalized_records() -> Any:
        """
        Return cleaned and standardized records for cross-source comparison.
        Edited by Qi: this endpoint maps web1 and web2 results into the same field structure.
        ---
        tags:
          - Results
        parameters:
          - name: path
            in: query
            required: false
            type: string
            description: JSONL file path. Defaults to testdata/results.jsonl.
        responses:
          200:
            description: Normalized records returned.
          404:
            description: File does not exist.
        """
        path = _resolve_path()
        if not os.path.exists(path):
            return jsonify({"error": f"File not found: {path}"}), 404

        normalized_rows, invalid_lines = iter_normalized_results(path)
        return jsonify(
            {
                "path": path,
                "normalized_results_path": normalized_output_path(path),
                "invalid_lines": invalid_lines,
                "records": normalized_rows,
            }
        )

    @app.get("/stress-benchmark-summary")
    def stress_benchmark_summary() -> Any:
        """
        Return the latest stress benchmark summary JSON for the monitoring dashboard.
        Edited by Qi: this endpoint lets the Dashboard load the final benchmark dataset without mixing old JSONL files.
        ---
        tags:
          - Results
        parameters:
          - name: path
            in: query
            required: false
            type: string
            description: Summary JSON file path. Defaults to testdata/stress_benchmarks/stress_benchmark_summary.json.
        responses:
          200:
            description: Stress benchmark summary returned.
          404:
            description: File does not exist.
        """
        path = request.args.get("path", "").strip() or "testdata/stress_benchmarks/stress_benchmark_summary.json"
        if not os.path.exists(path):
            return jsonify({"error": f"File not found: {path}"}), 404

        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            return jsonify({"error": f"Invalid JSON in summary file: {exc}"}), 400

        return jsonify({"path": path, "records": payload})

    @app.post("/normalize-results")
    def normalize_results_api() -> Any:
        """
        Create a cleaned JSONL file from an existing scraper results file.
        Edited by Qi: this API writes normalized records to disk for later review and comparison.
        ---
        tags:
          - Results
        parameters:
          - in: body
            name: body
            required: false
            schema:
              type: object
              properties:
                path:
                  type: string
                  example: testdata/results.jsonl
                output_path:
                  type: string
                  example: testdata/results.normalized.jsonl
        responses:
          200:
            description: Normalized JSONL file written successfully.
          404:
            description: Source file does not exist.
        """
        payload = request.get_json(silent=True) or {}
        path = str(payload.get("path") or default_results_path).strip()
        output_path = str(payload.get("output_path") or normalized_output_path(path)).strip()

        if not os.path.exists(path):
            return jsonify({"error": f"File not found: {path}"}), 404

        result = write_normalized_results(path, output_path=output_path)
        return jsonify(result)

    @app.route("/api/run-demo", methods=["POST", "OPTIONS"])
    def run_demo_api() -> Any:
        """
        Run the scraper demo from the React Run page.
        Edited by Qi: this API accepts the same inputs as main.py and returns a preview payload for the frontend.
        ---
        tags:
          - Run
        parameters:
          - in: body
            name: body
            required: false
            schema:
              type: object
              properties:
                addresses:
                  type: string
                  example: config/testlist.txt
                curl_config:
                  type: string
                  example: config/curl_config.txt
                results:
                  type: string
                  example: testdata/results.jsonl
                qps:
                  type: number
                  example: 2.0
                max_workers:
                  type: integer
                  example: 8
                initial_limit:
                  type: integer
                  example: 3
                limit:
                  type: integer
                  example: 100
                selected_sources:
                  type: array
                  items:
                    type: string
                  example: ["web1", "web2"]
        responses:
          200:
            description: Scraper run finished and preview data returned.
          400:
            description: Invalid request payload.
          404:
            description: Input file not found.
          500:
            description: Unexpected scraper error.
        """
        if request.method == "OPTIONS":
            return ("", 204)

        payload = request.get_json(silent=True) or {}

        try:
            config = _normalize_run_payload(payload)
        except ValueError as exc:
            return _json_error(str(exc), 400)

        results_path = Path(config["results"])
        if results_path.parent and str(results_path.parent) not in {".", ""}:
            results_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            run_demo(
                address_list_path=config["addresses"],
                curl_config_path=config["curl_config"],
                results_path=config["results"],
                qps=config["qps"],
                max_workers=config["max_workers"],
                initial_limit=config["initial_limit"],
                limit=config["limit"],
                selected_sources=config["selected_sources"],
            )
        except FileNotFoundError as exc:
            return _json_error(str(exc), 404)
        except ValueError as exc:
            return _json_error(str(exc), 400)
        except Exception as exc:  # noqa: BLE001
            return _json_error(f"Run failed: {exc}", 500)

        summary_data = summarize_results(config["results"])
        all_records, invalid_lines = iter_results(config["results"])
        normalized_records, _ = iter_normalized_results(config["results"])
        normalized_write_result = write_normalized_results(config["results"])

        return jsonify(
            {
                "status": "success",
                "message": "Run completed successfully.",
                "results_path": config["results"],
                "normalized_results_path": normalized_write_result["output_path"],
                "summary": summary_data,
                "records": all_records,
                "normalized_records": normalized_records,
                "invalid_lines": invalid_lines,
            }
        )

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    parser.add_argument("--results", default=DEFAULT_RESULTS_PATH, help="Default JSONL results file path")
    args = parser.parse_args()

    app = create_app(default_results_path=args.results)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
