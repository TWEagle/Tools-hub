#!/usr/bin/env python3
"""
tools/config_editor.py

Config editor (brand-agnostic) for Tools Hub.

What it does
- Lets an admin edit JSON/MD/TXT files under ./config (and ./config/profiles) from the browser.
- Uses the shared hub UI (app.layout) so it matches the rest of the portal.
- Simple safety:
  - Only files inside config/ are editable (no path traversal)
  - Optional allowlist of extensions
  - JSON files are validated before saving

Routes (default)
- GET/POST  /config-editor

Integration
- core.py registers this blueprint, typically via tools registry:
    from tools.config_editor import create_blueprint
    app.register_blueprint(create_blueprint(base_dir, get_settings, get_branding, get_tools_cfg))

Auth
- Uses the same "admin_ok" flag as your admin panel (Flask session cookie).
  If you're not logged in as admin, it redirects to /admin/login.

Notes
- This editor is meant for trusted use on localhost.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, request, redirect, url_for, render_template_string, session

try:
    from app.layout import common_css, header_html, footer_html, common_js
except Exception:  # pragma: no cover
    def common_css(settings: dict) -> str:
        return "body{font-family:Arial,sans-serif;background:#0b0b0b;color:#ddd;margin:0}.page{padding:20px}"
    def header_html(settings: dict, title: str, tools: list | None = None, right_html: str = "") -> str:
        return f"<div style='padding:12px 16px;border-bottom:1px solid #222;background:#111'><b>{title}</b></div>"
    def footer_html(settings: dict) -> str:
        return "<div style='padding:10px 16px;border-top:1px solid #222;background:#111;text-align:right;font-size:.9em'>© CyNiT 2024 - 2026</div>"
    def common_js() -> str:
        return ""

ADMIN_SESSION_KEY = "admin_ok"

# Editable extensions (you can extend this safely)
ALLOWED_EXTS = {".json", ".md", ".txt", ".yml", ".yaml"}


def _safe_rel(p: Path, base: Path) -> Optional[str]:
    """Return a posix relative path if p is under base, else None."""
    try:
        rp = p.resolve()
        base_r = base.resolve()
        rp.relative_to(base_r)
        return rp.relative_to(base_r).as_posix()
    except Exception:
        return None


def _list_editable_files(cfg_dir: Path) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    if not cfg_dir.exists():
        return items

    for p in sorted(cfg_dir.rglob("*")):
        if p.is_dir():
            continue
        if p.suffix.lower() not in ALLOWED_EXTS:
            continue
        rel = _safe_rel(p, cfg_dir)
        if not rel:
            continue
        items.append({"id": rel, "label": rel})
    return items


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _write_text(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _validate_json_if_needed(filename: str, text: str) -> Tuple[bool, Optional[str]]:
    if filename.lower().endswith(".json"):
        try:
            json.loads(text)
        except Exception as e:
            return False, f"JSON is niet geldig: {e}"
    return True, None


def create_blueprint(base_dir: Path, get_settings, get_branding, get_tools_cfg) -> Blueprint:
    bp = Blueprint("config_editor", __name__)

    cfg_dir = (base_dir / "config").resolve()

    def _is_admin() -> bool:
        return session.get(ADMIN_SESSION_KEY) is True

    def _require_admin():
        if not _is_admin():
            return redirect(url_for("admin.login", next=request.path))
        return None

    @bp.route("/config-editor", methods=["GET", "POST"])
    def index():
        guard = _require_admin()
        if guard:
            return guard

        settings = get_settings() or {}
        branding = get_branding() or {}
        tools_cfg = get_tools_cfg() or {"tools": []}
        tools = tools_cfg.get("tools", []) if isinstance(tools_cfg, dict) else []

        page_title = (branding.get("titles", {}) or {}).get("config_editor") or "Config editor"

        base_css = common_css(settings)
        js = common_js()
        header = header_html(settings, title=page_title, tools=tools)
        footer = footer_html(settings)

        files = _list_editable_files(cfg_dir)
        if not files:
            return render_template_string(
                "<!doctype html><html><body>{{header|safe}}<div class='page'>"
                "<h1>Config editor</h1><p>Geen bestanden gevonden in <code>config/</code>.</p>"
                "</div>{{footer|safe}}</body></html>",
                header=header, footer=footer
            )

        # current file selection
        current = (request.values.get("file") or files[0]["id"]).strip()
        # no traversal: only allow from list
        allowed_ids = {f["id"] for f in files}
        if current not in allowed_ids:
            current = files[0]["id"]

        cur_path = (cfg_dir / current).resolve()
        if _safe_rel(cur_path, cfg_dir) is None:
            current = files[0]["id"]
            cur_path = (cfg_dir / current).resolve()

        flashes: List[Tuple[str, str]] = []  # (level, message)
        content = _read_text(cur_path)

        if request.method == "POST":
            new_content = request.form.get("content") or ""
            ok, err = _validate_json_if_needed(current, new_content)
            if not ok:
                flashes.append(("err", err or "Ongeldig bestand."))
                content = new_content
            else:
                _write_text(cur_path, new_content)
                flashes.append(("ok", f"Opgeslagen: {current}"))
                content = new_content

        tmpl = r"""
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>{{ page_title }}</title>
  <style>
    {{ base_css|safe }}
    .panel{background:#0a0a0a;border:1px solid #222;border-radius:16px;padding:14px}
    .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
    select{padding:10px 12px;border-radius:12px;border:1px solid #333;background:#0b0b0b;color:{{ colors.general_fg }};min-width:320px}
    textarea{
      width:100%; min-height: 60vh; padding:12px; border-radius:14px;
      border:1px solid #333; background:#0b0b0b; color:{{ colors.general_fg }};
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 0.95rem; line-height:1.35;
      white-space: pre; overflow: auto;
    }
    .btnrow{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end;margin-top:12px}
    .tool-btn{display:inline-block;padding:10px 14px;border-radius:12px;border:1px solid #333;background:#111;color:#ddd;text-decoration:none;cursor:pointer}
    .tool-btn:hover{border-color: rgba(0,247,0,.35)}
    .flash-ok{background:#112211;border:1px solid #22aa22;padding:8px 10px;border-radius:10px;margin:10px 0;color:#bbf7d0}
    .flash-err{background:#221111;border:1px solid #aa3333;padding:8px 10px;border-radius:10px;margin:10px 0;color:#fecaca}
    .muted{opacity:.85}
    code{background:#111;padding:2px 6px;border-radius:8px;border:1px solid #222}
  </style>
  <script>{{ js|safe }}</script>
</head>
<body>
  {{ header|safe }}
  <div class="page">
    <div class="panel">
      <div class="row" style="justify-content:space-between;">
        <div>
          <h1 style="margin:0">{{ page_title }}</h1>
          <p class="muted" style="margin:6px 0 0 0">Bewerk files in <code>config/</code>. JSON wordt gevalideerd voor opslaan.</p>
        </div>
        <div class="row">
          <a class="tool-btn" href="{{ url_for('admin.panel') }}">Admin</a>
          <a class="tool-btn" href="{{ url_for('home.index') }}">Home</a>
        </div>
      </div>

      {% for level, msg in flashes %}
        <div class="{{ 'flash-ok' if level=='ok' else 'flash-err' }}">{{ msg }}</div>
      {% endfor %}

      <form method="post">
        <div class="row" style="margin-top:10px;">
          <label class="muted"><strong>Bestand</strong></label>
          <select name="file" onchange="this.form.submit()">
            {% for f in files %}
              <option value="{{ f.id }}" {{ 'selected' if f.id==current else '' }}>{{ f.label }}</option>
            {% endfor %}
          </select>
          <span class="muted">({{ current }})</span>
        </div>

        <textarea name="content" spellcheck="false">{{ content }}</textarea>

        <div class="btnrow">
          <button class="tool-btn" type="submit">Save</button>
        </div>
      </form>
    </div>
  </div>
  {{ footer|safe }}
</body>
</html>
"""
        colors = (settings.get("colors") or {}) if isinstance(settings, dict) else {}
        colors.setdefault("general_fg", "#ddd")

        return render_template_string(
            tmpl,
            base_css=base_css,
            js=js,
            header=header,
            footer=footer,
            colors=colors,
            page_title=page_title,
            files=files,
            current=current,
            content=content,
            flashes=flashes,
        )

    return bp
