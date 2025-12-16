from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List

from flask import Blueprint, current_app

bp = Blueprint("health", __name__)

START_TIME = time.time()
REQUEST_COUNT = 0


@dataclass
class HealthState:
    branding: Any
    settings: Dict[str, Any]
    tools: List[Dict[str, Any]]


@bp.before_app_request
def _count_requests():
    global REQUEST_COUNT
    REQUEST_COUNT += 1


@bp.get("/health")
def health():
    """
    Version is ONLY visible here (as requested).
    """
    st: HealthState = current_app.config["HUB_STATE"]
    uptime = time.time() - START_TIME
    dev_mode = bool(st.settings.get("dev_mode", False))

    data = {
        "status": "ok",
        "uptime_seconds": round(uptime, 2),
        "brand": {
            "id": st.branding.brand_id,
            "name": st.branding.name,
            "version": st.branding.version,   # <-- only here
        },
        "dev_mode": dev_mode,
        "tools_loaded": len(st.tools),
    }
    return data, 200


@bp.get("/metrics")
def metrics():
    """
    Simple text metrics (Prometheus-ish).
    """
    st: HealthState = current_app.config["HUB_STATE"]
    uptime = time.time() - START_TIME
    dev_mode = 1 if bool(st.settings.get("dev_mode", False)) else 0

    lines = [
        "# HELP tools_hub_uptime_seconds Uptime in seconds.",
        "# TYPE tools_hub_uptime_seconds gauge",
        f"tools_hub_uptime_seconds {uptime:.0f}",
        "",
        "# HELP tools_hub_requests_total Total HTTP requests since start.",
        "# TYPE tools_hub_requests_total counter",
        f"tools_hub_requests_total {REQUEST_COUNT}",
        "",
        "# HELP tools_hub_tools_loaded Tools loaded from tools.json.",
        "# TYPE tools_hub_tools_loaded gauge",
        f"tools_hub_tools_loaded {len(st.tools)}",
        "",
        "# HELP tools_hub_dev_mode Dev mode enabled (1/0).",
        "# TYPE tools_hub_dev_mode gauge",
        f"tools_hub_dev_mode {dev_mode}",
    ]
    return "\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; version=0.0.4"}
