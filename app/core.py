from __future__ import annotations

import importlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, send_from_directory

from .branding import Branding, load_branding
from .theme import load_settings, load_tools
from .health import bp as health_bp, HealthState
from .home import bp as home_bp


@dataclass
class HubState:
    branding: Branding
    settings: Dict[str, Any]
    tools: List[Dict[str, Any]]


def _safe_print(msg: str) -> None:
    # avoid unicode console crashes on work PCs
    try:
        print(str(msg))
    except Exception:
        try:
            print(str(msg).encode("ascii", "ignore").decode("ascii"))
        except Exception:
            pass


def _sort_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(tools, key=lambda x: (x.get("name") or x.get("id") or "").lower())


def _load_registry(base_dir: Path) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    tools_cfg = load_tools(base_dir)
    raw_tools = tools_cfg.get("tools", [])
    if not isinstance(raw_tools, list):
        raw_tools = []

    settings = load_settings(base_dir)
    dev_mode = bool(settings.get("dev_mode", False))

    # filter hidden unless dev_mode
    out = []
    for t in raw_tools:
        if not isinstance(t, dict):
            continue
        if t.get("hidden") and not dev_mode:
            continue
        out.append(t)

    return tools_cfg, _sort_tools(out)


def _register_tool_routes(app: Flask, base_dir: Path, settings: Dict[str, Any], tools: List[Dict[str, Any]]) -> None:
    """
    Each tool can define:
      - "module": "cert_viewer" (imports tools.cert_viewer)
      and inside module: register_web_routes(app, settings, tools)
    """
    _safe_print(">>> REGISTERING TOOL ROUTES")
    for t in tools:
        modname = t.get("module")
        if not modname:
            continue
        try:
            module = importlib.import_module(f"tools.{modname}")
            fn = getattr(module, "register_web_routes", None)
            if callable(fn):
                fn(app, settings, tools)
                _safe_print(f" - OK: {modname} routes registered")
            else:
                _safe_print(f" - SKIP: {modname} has no register_web_routes()")
        except Exception as exc:
            _safe_print(f" - ERROR: {modname} register failed: {exc}")


def _gui_launcher_factory(base_dir: Path):
    """
    Default GUI launcher used by /start/ in home.py.
    It runs tool["script"] with current python.
    """
    def launch(tool: Dict[str, Any]) -> None:
        script = tool.get("script")
        if not script:
            return
        script_path = (base_dir / script).resolve()
        if not script_path.exists():
            _safe_print(f"[WARN] GUI script not found: {script_path}")
            return
        try:
            subprocess.Popen([sys.executable, str(script_path)], cwd=str(base_dir))
        except Exception as e:
            _safe_print(f"[ERROR] GUI start failed: {e}")

    return launch


def create_app(base_dir: str | Path | None = None) -> Flask:
    """
    App factory for run.py
    """
    if base_dir is None:
        # run.py sits at repo root
        base = Path(__file__).resolve().parents[1]
    else:
        base = Path(base_dir).resolve()

    branding = load_branding(base)
    settings = load_settings(base)
    _tools_cfg, tools = _load_registry(base)

    app = Flask(__name__)
    app.secret_key = str(settings.get("secret_key", "dev-secret"))

    # store state
    st = HubState(branding=branding, settings=settings, tools=tools)
    app.config["HUB_STATE"] = HealthState(branding=branding, settings=settings, tools=tools)
    app.config["GUI_LAUNCHER"] = _gui_launcher_factory(base)

    # blueprints
    app.register_blueprint(home_bp)
    app.register_blueprint(health_bp)

    # restart endpoint (reload config in-memory)
    @app.get("/restart")
    def restart():
        nonlocal branding, settings, tools, st
        branding = load_branding(base)
        settings = load_settings(base)
        _tools_cfg2, tools2 = _load_registry(base)
        tools = tools2
        st = HubState(branding=branding, settings=settings, tools=tools)

        # update shared config used by blueprints
        app.config["HUB_STATE"] = HealthState(branding=branding, settings=settings, tools=tools)
        app.secret_key = str(settings.get("secret_key", "dev-secret"))

        # re-register tool routes is tricky (Flask doesn't support clean “unregister”).
        # For now: only refresh data (UI/settings/tools). A full restart is via launcher.
        return "OK", 200

    # Serve assets (logo/favicon/etc)
    @app.get("/assets/<path:filename>")
    def assets(filename: str):
        return send_from_directory(str(base), filename)

    # Register external tool routes (web tools)
    _register_tool_routes(app, base, settings, tools)

    return app
