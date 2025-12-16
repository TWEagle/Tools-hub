from __future__ import annotations

import time
from typing import Any, Dict
from flask import Blueprint, jsonify, g, request

REQUEST_COUNT = 0

def register_health(app, state: Dict[str, Any] | None = None) -> None:
    bp = Blueprint("health", __name__)

    @app.before_request
    def _track_request():
        global REQUEST_COUNT
        REQUEST_COUNT += 1
        g.request_started = time.time()

    @bp.get("/health")
    def health():
        return jsonify({"ok": True, "ts": time.time()})

    @bp.get("/metrics")
    def metrics():
        # very simple metrics
        return (
            f"cynit_requests_total {REQUEST_COUNT}\n",
            200,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    app.register_blueprint(bp)
