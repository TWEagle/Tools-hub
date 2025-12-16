# app/health.py
from __future__ import annotations

import time
from flask import Flask

START_TIME = time.time()
REQUEST_COUNT = 0


def register_health_routes(app: Flask, get_settings, get_branding, get_tools_cfg) -> None:
    @app.before_request
    def _count():
        global REQUEST_COUNT
        REQUEST_COUNT += 1

    @app.route("/health")
    def health():
        branding = get_branding() or {}
        settings = get_settings() or {}
        tools_cfg = get_tools_cfg() or {}

        version = str(branding.get("version") or "").strip()  # only visible here if you want
        uptime = time.time() - START_TIME

        data = {
            "status": "ok",
            "uptime_seconds": round(uptime, 2),
            "tools_total": len(tools_cfg.get("tools", []) or []),
            "dev_mode": bool(settings.get("dev_mode", False)),
        }
        if version:
            data["version"] = version
        return data, 200

    @app.route("/metrics")
    def metrics():
        uptime = time.time() - START_TIME
        lines = [
            "# HELP tools_hub_uptime_seconds Uptime in seconds.",
            "# TYPE tools_hub_uptime_seconds gauge",
            f"tools_hub_uptime_seconds {uptime:.0f}",
            "",
            "# HELP tools_hub_requests_total HTTP requests since start.",
            "# TYPE tools_hub_requests_total counter",
            f"tools_hub_requests_total {REQUEST_COUNT}",
        ]
        body = "\n".join(lines) + "\n"
        return body, 200, {"Content-Type": "text/plain; version=0.0.4"}
