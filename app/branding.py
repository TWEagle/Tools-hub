from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

# Project root = folder that contains /app, /config, /tools, ...
ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT_DIR / "config"
BRANDING_PATH = CONFIG_DIR / "branding.json"

_DEFAULT: Dict[str, Any] = {
    "brand_id": "tools-hub",
    "app_name": "Tools Hub",
    "window_title": "Tools Hub",
    "tray_title": "Tools Hub",
    "header_title": "Tools Hub",
    "popup_title": "Tools Hub",
    "company": "",
    "assets": {
        "logo_web": "assets/logos/logo.png",
        "logo_tray": "assets/logos/logo.png",
        "favicon": "assets/icons/favicon.ico",
    },
    "cert": {
        "common_name": "localhost",
        "cert_filename": "localhost.crt",
        "key_filename": "localhost.key",
    },
}

_BRAND: Dict[str, Any] | None = None


def load_branding(force_reload: bool = False) -> Dict[str, Any]:
    global _BRAND
    if _BRAND is not None and not force_reload:
        return _BRAND

    data = dict(_DEFAULT)
    try:
        if BRANDING_PATH.exists():
            raw = json.loads(BRANDING_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update(raw)
                # deep merge for nested dicts we care about
                for k in ("assets", "cert"):
                    if isinstance(_DEFAULT.get(k), dict):
                        merged = dict(_DEFAULT[k])
                        if isinstance(raw.get(k), dict):
                            merged.update(raw[k])
                        data[k] = merged
    except Exception:
        # keep defaults if branding is broken
        pass

    _BRAND = data
    return data


def brand() -> Dict[str, Any]:
    return load_branding(False)


def app_name() -> str:
    return str(brand().get("app_name") or "Tools Hub")


def window_title() -> str:
    return str(brand().get("window_title") or app_name())


def tray_title() -> str:
    return str(brand().get("tray_title") or app_name())


def header_title() -> str:
    return str(brand().get("header_title") or app_name())


def popup_title() -> str:
    return str(brand().get("popup_title") or app_name())


def asset_path(key: str, default: str = "") -> str:
    assets = brand().get("assets", {})
    if isinstance(assets, dict) and assets.get(key):
        return str(assets[key])
    return default


def cert_common_name() -> str:
    c = brand().get("cert", {})
    if isinstance(c, dict) and c.get("common_name"):
        return str(c["common_name"])
    return "localhost"


def cert_filenames() -> tuple[str, str]:
    c = brand().get("cert", {})
    crt = "localhost.crt"
    key = "localhost.key"
    if isinstance(c, dict):
        crt = str(c.get("cert_filename") or crt)
        key = str(c.get("key_filename") or key)
    return crt, key
