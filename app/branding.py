from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


_TOKEN_RE = re.compile(r"\{([a-zA-Z0-9_.-]+)\}")


def _deep_get(d: Dict[str, Any], key: str, default: Any = "") -> Any:
    cur: Any = d
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def format_tokens(template: str, ctx: Dict[str, Any]) -> str:
    """
    Replaces {brand.name} etc with values from ctx.
    Unknown tokens -> empty string.
    """
    if not isinstance(template, str):
        return str(template)

    def repl(m: re.Match) -> str:
        key = m.group(1)
        val = _deep_get(ctx, key, "")
        return "" if val is None else str(val)

    return _TOKEN_RE.sub(repl, template)


def expand_templates(obj: Any, ctx: Dict[str, Any]) -> Any:
    """
    Recursively expands strings containing {tokens}.
    """
    if isinstance(obj, str):
        return format_tokens(obj, ctx)
    if isinstance(obj, list):
        return [expand_templates(x, ctx) for x in obj]
    if isinstance(obj, dict):
        return {k: expand_templates(v, ctx) for k, v in obj.items()}
    return obj


@dataclass(frozen=True)
class Branding:
    raw: Dict[str, Any]
    base_dir: Path

    @property
    def brand_id(self) -> str:
        return str(self.raw.get("brand", {}).get("id", "tools-hub"))

    @property
    def name(self) -> str:
        return str(self.raw.get("brand", {}).get("name", "Tools Hub"))

    @property
    def version(self) -> str:
        return str(self.raw.get("brand", {}).get("version", "0.0.0"))

    @property
    def copyright(self) -> str:
        return str(self.raw.get("brand", {}).get("copyright", ""))

    def ui_value(self, key: str, default: str = "") -> str:
        return str(self.raw.get("ui", {}).get(key, default))

    def asset_path(self, key: str) -> str:
        """
        Returns asset path string (relative preferred).
        """
        return str(self.raw.get("assets", {}).get(key, ""))

    def cert_filename(self, key: str, default: str) -> str:
        return str(self.raw.get("cert", {}).get(key, default))

    def cert_alt_names(self) -> list[str]:
        alts = self.raw.get("cert", {}).get("alt_names", ["localhost", "127.0.0.1", "::1"])
        if not isinstance(alts, list):
            return ["localhost", "127.0.0.1", "::1"]
        return [str(x) for x in alts if str(x).strip()]


def load_branding(base_dir: Path) -> Branding:
    """
    Loads config/branding.json and expands templates.
    """
    cfg_path = base_dir / "config" / "branding.json"
    raw: Dict[str, Any] = {}

    if cfg_path.exists():
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    else:
        raw = {
            "brand": {"id": "tools-hub", "name": "Tools Hub", "version": "0.0.0", "copyright": ""},
            "ui": {"window_title": "{brand.name}", "header_title": "{brand.name}", "tray_title": "{brand.name}"},
            "assets": {"logo": "", "favicon": "", "tray_icon": ""},
            "cert": {
                "common_name": "localhost",
                "alt_names": ["localhost", "127.0.0.1", "::1"],
                "cert_file": "localhost.crt",
                "key_file": "localhost.key",
            },
        }

    ctx = {"brand": raw.get("brand", {}), "ui": raw.get("ui", {}), "assets": raw.get("assets", {}), "cert": raw.get("cert", {})}
    expanded = expand_templates(raw, ctx)
    return Branding(raw=expanded, base_dir=base_dir)
