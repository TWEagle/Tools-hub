from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


DEFAULTS: Dict[str, Any] = {
    "colors": {
        "background": "#000000",
        "general_fg": "#00FA00",
        "title": "#00A2FF",
        "button_bg": "#111111",
        "button_fg": "#00B7C3",
    },
    "ui": {
        "font_main": "Consolas",
        "font_buttons": "Segoe UI",
        "logo_max_height": 80,
    },
    "paths": {
        "logo": "assets/logos/logo.png",
        "help": "ABOUT.md",
    },
    "dev_mode": False,
    "home_columns": 3,
}


def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings(base_dir: Path) -> Dict[str, Any]:
    """
    Loads config/settings.json with profile overlay (active_profile).
    Keeps it brand-agnostic.
    """
    cfg = DEFAULTS
    path = base_dir / "config" / "settings.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        cfg = _deep_merge(cfg, data)

    # optional profile overlay
    active = cfg.get("active_profile")
    profiles = cfg.get("profiles")
    if active and isinstance(profiles, dict) and active in profiles and isinstance(profiles[active], dict):
        cfg = _deep_merge(cfg, profiles[active])

    return cfg


def load_tools(base_dir: Path) -> Dict[str, Any]:
    """
    Loads config/tools.json (registry).
    """
    path = base_dir / "config" / "tools.json"
    if not path.exists():
        return {"tools": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"tools": []}
    if "tools" not in data or not isinstance(data["tools"], list):
        data["tools"] = []
    return data
