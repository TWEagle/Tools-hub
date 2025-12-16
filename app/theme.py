from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from . import branding

ROOT_DIR = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT_DIR  # backwards-friendly alias
CONFIG_DIR = ROOT_DIR / "config"

_SETTINGS_CACHE: Dict[str, Any] | None = None
_TOOLS_CACHE: Dict[str, Any] | None = None


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings(force_reload: bool = False) -> Dict[str, Any]:
    """Load config/settings.json, apply active profile (if present), and attach branding."""
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None and not force_reload:
        return _SETTINGS_CACHE

    settings_path = CONFIG_DIR / "settings.json"
    data = _read_json(settings_path, {}) or {}

    # Apply profile overlay: settings.profiles[active_profile]
    active = data.get("active_profile")
    profiles = data.get("profiles")
    if isinstance(active, str) and isinstance(profiles, dict):
        prof = profiles.get(active)
        if isinstance(prof, dict):
            # merge profile on top of root settings (but keep profiles itself)
            preserved_profiles = data.get("profiles")
            data = _deep_merge(data, prof)
            data["profiles"] = preserved_profiles

    # Attach branding for convenience
    data["branding"] = branding.brand()

    _SETTINGS_CACHE = data
    return data


def load_tools(force_reload: bool = False) -> Dict[str, Any]:
    global _TOOLS_CACHE
    if _TOOLS_CACHE is not None and not force_reload:
        return _TOOLS_CACHE

    tools_path = CONFIG_DIR / "tools.json"
    data = _read_json(tools_path, {}) or {}
    if not isinstance(data, dict):
        data = {}

    _TOOLS_CACHE = data
    return data


def reset_cache() -> None:
    global _SETTINGS_CACHE, _TOOLS_CACHE
    _SETTINGS_CACHE = None
    _TOOLS_CACHE = None
