from __future__ import annotations

import argparse
import os
from typing import Any

from flasgger import Swagger
from flask import Flask, jsonify, request

from src.results_reader import read_recent_records, summarize_results


def create_app(default_results_path: str = "testdata/results.jsonl") -> Flask:
    app = Flask(__name__)
    app.config["SWAGGER"] = {
        "title": "Scraper API",
        "uiversion": 3,
    }

    template: dict[str, Any] = {
        "swagger": "2.0",
        "info": {
            "title": "Scraper API",
            "description": "Swagger 2 endpoints for scraper health and JSONL analytics.",
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

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    parser.add_argument("--results", default="testdata/results.jsonl", help="Default JSONL results file path")
    args = parser.parse_args()

    app = create_app(default_results_path=args.results)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
