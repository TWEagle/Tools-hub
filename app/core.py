# app/core.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from flask import Flask

from .home import create_home_blueprint
from .admin import create_admin_blueprint
from .health import register_health_routes
from .help import create_help_blueprint


def _read_json(path: Path, default: dict) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def create_app(base_dir: Path) -> Flask:
    app = Flask(__name__)

    # ---- config paths
    cfg_dir = base_dir / "config"
    settings_path = cfg_dir / "settings.json"
    branding_path = cfg_dir / "branding.json"
    tools_path = cfg_dir / "tools.json"
    help_path = cfg_dir / "help.json"

    # ---- state
    state: Dict[str, Any] = {
        "settings": {},
        "branding": {},
        "tools_cfg": {"tools": []},
        "help_cfg": {"docs": []},
    }

    def reload_all() -> None:
        state["settings"] = _read_json(settings_path, {})
        state["branding"] = _read_json(branding_path, {"app_title": "Centraal Portaal"})
        state["tools_cfg"] = _read_json(tools_path, {"tools": []})
        state["help_cfg"] = _read_json(help_path, {"docs": []})

    def get_settings() -> dict:
        return state.get("settings") or {}

    def get_branding() -> dict:
        return state.get("branding") or {}

    def get_tools_cfg() -> dict:
        return state.get("tools_cfg") or {"tools": []}

    def set_tools_cfg(data: dict) -> None:
        state["tools_cfg"] = data or {"tools": []}
        _write_json(tools_path, state["tools_cfg"])

    def get_help_cfg() -> dict:
        return state.get("help_cfg") or {"docs": []}

    def set_help_cfg(data: dict) -> None:
        state["help_cfg"] = data or {"docs": []}
        _write_json(help_path, state["help_cfg"])

    # initial load
    reload_all()

    # secret key
    app.secret_key = (get_settings().get("secret_key") or "dev-key").strip()

    # blueprints
    app.register_blueprint(create_home_blueprint(get_settings, get_branding, get_tools_cfg))
    app.register_blueprint(create_help_blueprint(base_dir, get_settings, get_branding, get_help_cfg))
    app.register_blueprint(
        create_admin_blueprint(
            base_dir=base_dir,
            settings=get_settings(),
            branding=get_branding(),
            get_tools_cfg=get_tools_cfg,
            set_tools_cfg=set_tools_cfg,
            get_help_cfg=get_help_cfg,
            set_help_cfg=set_help_cfg,
        )
    )
    
    
    # health
    register_health_routes(app, get_settings, get_branding, get_tools_cfg)

    # simple reload endpoint (optional)
    @app.route("/reload")
    def reload_route():
        reload_all()
        return {"status": "ok"}, 200

    return app
