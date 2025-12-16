from __future__ import annotations

import importlib
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, redirect, request, send_from_directory, jsonify

from . import branding, theme, home, health

ROOT_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT_DIR / "assets"
CONFIG_DIR = ROOT_DIR / "config"


def _safe_stdout_utf8() -> None:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _normalize_tool_list(tools_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    tools = tools_cfg.get("tools", [])
    if not isinstance(tools, list):
        return []
    out: List[Dict[str, Any]] = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        out.append(t)
    return out


def _register_tool_modules(app: Flask, settings: Dict[str, Any], tools_cfg: Dict[str, Any]) -> None:
    tools_list = _normalize_tool_list(tools_cfg)

    # Import unique python modules referenced by tools.json (script field)
    scripts = []
    for t in tools_list:
        script = t.get("script")
        if isinstance(script, str) and script.endswith(".py"):
            scripts.append(script[:-3])
        elif isinstance(script, str):
            # allow bare module name
            scripts.append(script)

    for mod_name in sorted(set(scripts)):
        if not mod_name:
            continue
        # expected in tools/ package
        try:
            mod = importlib.import_module(f"tools.{mod_name}")
        except Exception as e:
            print(f"[WARN] tool module import failed: tools.{mod_name}: {e}")
            continue

        # convention: register_web_routes(app, settings, tools_cfg)
        fn = getattr(mod, "register_web_routes", None)
        if callable(fn):
            try:
                fn(app, settings, tools_cfg)
                print(f"[OK] routes registered: {mod_name}")
            except Exception as e:
                print(f"[WARN] register_web_routes failed: {mod_name}: {e}")


def create_app() -> Flask:
    _safe_stdout_utf8()

    app = Flask(__name__)
    app.secret_key = str(theme.load_settings().get("secret_key", "tools-hub-secret"))

    # ---------- static assets ----------
    @app.get("/assets/<path:subpath>")
    def _assets(subpath: str):
        return send_from_directory(str(ASSETS_DIR), subpath)

    @app.get("/favicon.ico")
    def _favicon():
        fav = branding.asset_path("favicon", "assets/icons/favicon.ico")
        # allow both /assets/... and direct file
        if fav.startswith("assets/"):
            return redirect("/" + fav)
        return redirect("/assets/icons/favicon.ico")

    # ---------- config images/help passthrough ----------
    @app.get("/ABOUT.md")
    def _about_md():
        p = ROOT_DIR / "ABOUT.md"
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace"), 200, {"Content-Type": "text/plain; charset=utf-8"}
        return "ABOUT.md missing", 404

    # ---------- runtime state ----------
    state: Dict[str, Any] = {
        "restart_requested": False,
    }

    def reload_all() -> tuple[Dict[str, Any], Dict[str, Any]]:
        theme.reset_cache()
        branding.load_branding(force_reload=True)
        settings = theme.load_settings(force_reload=True)
        tools_cfg = theme.load_tools(force_reload=True)
        return settings, tools_cfg

    settings, tools_cfg = reload_all()

    # ---------- core routes ----------
    @app.get("/")
    def index():
        nonlocal settings, tools_cfg
        settings, tools_cfg = reload_all() if settings.get("dev_mode") else (settings, tools_cfg)
        tools_list = _normalize_tool_list(tools_cfg)
        return home.render_home(tools=tools_list, settings=settings, dev_mode=bool(settings.get("dev_mode")))

    @app.post("/start/")
    def start_tool_gui():
        # Keeps compatibility with your existing GUI-start flow:
        # tools.json: id + type + script
        tool_id = request.form.get("tool_id", "")
        tools_list = _normalize_tool_list(tools_cfg)
        tool = next((t for t in tools_list if str(t.get("id")) == str(tool_id)), None)
        if not tool:
            return "Tool not found", 404

        script = tool.get("script")
        if not script:
            return "Tool script missing", 400

        # We run it in a new process (best effort). GUI tools should accept --gui if needed.
        cmd = [sys.executable, str(ROOT_DIR / "tools" / script), "--gui"]
        try:
            import subprocess
            subprocess.Popen(cmd, cwd=str(ROOT_DIR), creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0)
        except Exception as e:
            return f"Failed to start tool: {e}", 500
        return redirect("/")

    @app.get("/reload-config")
    def reload_config():
        nonlocal settings, tools_cfg
        settings, tools_cfg = reload_all()
        return jsonify({"ok": True})

    @app.get("/restart")
    def restart():
        # Launcher should handle restart by killing process; this endpoint is just for UI convenience.
        state["restart_requested"] = True
        return jsonify({"ok": True})

    # ---------- health ----------
    health.register_health(app, state)

    # ---------- register tool web routes ----------
    _register_tool_modules(app, settings, tools_cfg)

    return app
