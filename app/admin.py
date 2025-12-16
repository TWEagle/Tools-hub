# app/admin.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from flask import Blueprint, request, redirect, url_for, session, render_template_string

from .layout import common_css, header_html, footer_html, common_js


def _safe_read_json(path: Path, default: dict) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _safe_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _normalize_categories(items: list[dict], key: str = "category") -> list[str]:
    cats = []
    seen = set()
    for it in items:
        c = (it.get(key) or "misc").strip() or "misc"
        if c not in seen:
            seen.add(c)
            cats.append(c)
    if "misc" not in seen:
        cats.append("misc")
    return cats


def _enabled_default(it: dict) -> bool:
    # backward compatible: missing "enabled" means enabled
    return bool(it.get("enabled", True))


def _get_admin_pin(settings: dict, branding: dict) -> str:
    # Priority: settings.secrets.admin_pin -> settings.secrets.yt_pin -> branding.secrets.admin_pin -> "3990"
    pin = None
    secrets = settings.get("secrets", {}) if isinstance(settings, dict) else {}
    if isinstance(secrets, dict):
        pin = secrets.get("admin_pin") or secrets.get("yt_pin")

    if not pin:
        bsec = branding.get("secrets", {}) if isinstance(branding, dict) else {}
        if isinstance(bsec, dict):
            pin = bsec.get("admin_pin")

    return str(pin or "3990").strip()


def create_admin_blueprint(
    base_dir: Path,
    settings: dict,
    branding: dict,
    get_tools_cfg,
    set_tools_cfg,
    get_help_cfg,
    set_help_cfg,
) -> Blueprint:
    """
    get_tools_cfg() -> dict
    set_tools_cfg(dict) -> None
    get_help_cfg() -> dict
    set_help_cfg(dict) -> None
    """

    bp = Blueprint("admin", __name__)

    ADMIN_SESSION_KEY = "admin_ok"

    def _is_admin() -> bool:
        return session.get(ADMIN_SESSION_KEY) is True

    def _require_admin():
        if not _is_admin():
            return redirect(url_for("admin.login", next=request.path))
        return None

    @bp.route("/admin/login", methods=["GET", "POST"])
    def login():
        colors = settings.get("colors", {})
        base_css = common_css(settings)
        js = common_js()
        header = header_html(settings, title="Admin login", tools=[])
        footer = footer_html()

        next_url = request.args.get("next") or url_for("admin.panel")

        err = None
        if request.method == "POST":
            pin = (request.form.get("pin") or "").strip()
            expected = _get_admin_pin(settings, branding)
            if pin == expected:
                session[ADMIN_SESSION_KEY] = True
                return redirect(next_url)
            err = "Foute PIN."

        tmpl = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>Admin login</title>
  <style>{{ base_css|safe }}</style>
  <script>{{ js|safe }}</script>
</head>
<body>
  {{ header|safe }}
  <div class="page" style="max-width:520px;">
    <h1>Admin login</h1>
    <p class="muted">Geef de admin PIN in om tools/help te beheren.</p>

    {% if err %}
      <div class="flash-err">{{ err }}</div>
    {% endif %}

    <form method="post">
      <label><strong>PIN</strong></label>
      <input name="pin" type="password" autofocus
             style="width:100%;padding:10px;border-radius:10px;border:1px solid #333;background:#0b0b0b;color:{{ colors.general_fg }};font-size:1.1rem;letter-spacing:3px;text-align:center;">
      <div style="margin-top:12px;">
        <button class="tool-btn" type="submit">Login</button>
        <a class="tool-btn" href="{{ url_for('home.index') }}">Terug</a>
      </div>
    </form>
  </div>
  {{ footer|safe }}
</body>
</html>
        """
        return render_template_string(
            tmpl, base_css=base_css, js=js, header=header, footer=footer, err=err, colors=colors
        )

    @bp.route("/admin/logout")
    def logout():
        session.pop(ADMIN_SESSION_KEY, None)
        return redirect(url_for("home.index"))

    @bp.route("/admin", methods=["GET"])
    def panel():
        guard = _require_admin()
        if guard:
            return guard

        colors = settings.get("colors", {})
        base_css = common_css(settings)
        js = common_js()
        header = header_html(settings, title="Admin panel", tools=[])
        footer = footer_html()

        tools_cfg = get_tools_cfg() or {"tools": []}
        help_cfg = get_help_cfg() or {"docs": []}

        tools = tools_cfg.get("tools", []) if isinstance(tools_cfg, dict) else []
        docs = help_cfg.get("docs", []) if isinstance(help_cfg, dict) else []

        # normalize fields (backward compatible)
        for t in tools:
            t.setdefault("enabled", True)
            t["enabled"] = _enabled_default(t)
            t.setdefault("category", "misc")
            t["category"] = (t.get("category") or "misc").strip() or "misc"

        for d in docs:
            d.setdefault("enabled", True)
            d["enabled"] = _enabled_default(d)
            d.setdefault("category", "misc")
            d["category"] = (d.get("category") or "misc").strip() or "misc"
            d.setdefault("title", d.get("id", "doc"))

        tool_categories = tools_cfg.get("categories")
        if not isinstance(tool_categories, list):
            tool_categories = [{"id": c, "label": c.title()} for c in _normalize_categories(tools)]

        help_categories = help_cfg.get("categories")
        if not isinstance(help_categories, list):
            help_categories = [{"id": c, "label": c.title()} for c in _normalize_categories(docs)]

        # Tab selection
        tab = (request.args.get("tab") or "tools").strip().lower()
        if tab not in ("tools", "help"):
            tab = "tools"

        tmpl = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>Admin</title>
  <style>
    {{ base_css|safe }}

    .tabs { display:flex; gap:10px; margin: 10px 0 18px 0; }
    .tab {
      padding: 8px 14px; border-radius: 999px; border: 1px solid #333;
      background: #0b0b0b; color: {{ colors.general_fg }};
      cursor: pointer; text-decoration:none;
    }
    .tab.active { border-color: rgba(0,247,0,0.35); background:#121212; }

    .panel { background:#0a0a0a;border:1px solid #222;border-radius:16px;padding:14px; }
    .row { display:grid; grid-template-columns: 1.1fr 1.6fr 0.9fr 0.8fr; gap:10px; align-items:center; padding:8px 0; border-bottom:1px solid #141414; }
    .row:last-child { border-bottom:none; }
    .small { font-size:0.9rem; color:#aaa; }
    input[type="text"] { width:100%; padding:8px 10px; border-radius:10px; border:1px solid #333; background:#0b0b0b; color: {{ colors.general_fg }}; }
    select { width:100%; padding:8px 10px; border-radius:10px; border:1px solid #333; background:#0b0b0b; color: {{ colors.general_fg }}; }
    .right { display:flex; gap:10px; justify-content:flex-end; }
    .flash-ok { background:#112211; border:1px solid #22aa22; padding:8px 10px; border-radius:10px; margin-bottom:10px; color:#bbf7d0; }
    .flash-err { background:#221111; border:1px solid #aa3333; padding:8px 10px; border-radius:10px; margin-bottom:10px; color:#fecaca; }

    .catbar { display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 12px; }
    .catpill { padding:6px 10px; border-radius:999px; border:1px solid #333; background:#0b0b0b; color:#ddd; font-size:0.9rem; }
    .catpill button { margin-left:8px; }
    .tool-btn { margin:0; }
  </style>
  <script>{{ js|safe }}</script>
</head>
<body>
  {{ header|safe }}
  <div class="page">
    <div class="right" style="margin-top:8px;">
      <a class="tool-btn" href="{{ url_for('admin.logout') }}">Logout</a>
      <a class="tool-btn" href="{{ url_for('home.index') }}">Home</a>
    </div>

    <h1>Admin panel</h1>
    <p class="muted">Beheer welke tools en help-pagina’s zichtbaar zijn in de normale UI. (Admin ziet alles.)</p>

    <div class="tabs">
      <a class="tab {{ 'active' if tab=='tools' else '' }}" href="{{ url_for('admin.panel', tab='tools') }}">Tools</a>
      <a class="tab {{ 'active' if tab=='help' else '' }}" href="{{ url_for('admin.panel', tab='help') }}">Help</a>
    </div>

    {% if tab == 'tools' %}
      <div class="panel">
        <h2>Tools</h2>
        <p class="small">Toggle <strong>enabled</strong> en pas <strong>category</strong> aan. Save schrijft naar <code>config/tools.json</code>.</p>

        <form method="post" action="{{ url_for('admin.save_tools') }}">
          <div class="catbar">
            {% for c in tool_categories %}
              <span class="catpill">
                {{ c.label }}
                <button class="tool-btn" type="submit" name="cat_action" value="enable:{{ c.id }}">Enable</button>
                <button class="tool-btn" type="submit" name="cat_action" value="disable:{{ c.id }}">Disable</button>
              </span>
            {% endfor %}
          </div>

          <div class="row" style="font-weight:700;">
            <div>Naam</div><div>Beschrijving / Path</div><div>Categorie</div><div>Enabled</div>
          </div>

          {% for t in tools %}
            <div class="row">
              <div>
                <div><strong>{{ t.name }}</strong></div>
                <div class="small">id: {{ t.id }}</div>
              </div>
              <div class="small">
                <div>{{ t.description or '' }}</div>
                <div>web: {{ t.web_path or '-' }} · script: {{ t.script or '-' }}</div>
              </div>
              <div>
                <select name="tool_category__{{ t.id }}">
                  {% for c in tool_categories %}
                    <option value="{{ c.id }}" {{ 'selected' if t.category==c.id else '' }}>{{ c.label }}</option>
                  {% endfor %}
                </select>
              </div>
              <div>
                <label style="display:flex;align-items:center;gap:10px;justify-content:flex-end;">
                  <input type="checkbox" name="tool_enabled__{{ t.id }}" value="1" {{ 'checked' if t.enabled else '' }}>
                  <span>{{ 'ON' if t.enabled else 'OFF' }}</span>
                </label>
              </div>
            </div>
          {% endfor %}

          <div class="right" style="margin-top:14px;">
            <button class="tool-btn" type="submit" name="save" value="1">Save Tools</button>
          </div>
        </form>
      </div>

    {% else %}
      <div class="panel">
        <h2>Help</h2>
        <p class="small">Beheer Markdown docs. Save schrijft naar <code>config/help.json</code>.</p>

        <form method="post" action="{{ url_for('admin.save_help') }}">
          <div class="catbar">
            {% for c in help_categories %}
              <span class="catpill">
                {{ c.label }}
                <button class="tool-btn" type="submit" name="cat_action" value="enable:{{ c.id }}">Enable</button>
                <button class="tool-btn" type="submit" name="cat_action" value="disable:{{ c.id }}">Disable</button>
              </span>
            {% endfor %}
          </div>

          <div class="row" style="font-weight:700; grid-template-columns: 1.1fr 1.6fr 0.9fr 0.8fr;">
            <div>Titel</div><div>Pad</div><div>Categorie</div><div>Enabled</div>
          </div>

          {% for d in docs %}
            <div class="row" style="grid-template-columns: 1.1fr 1.6fr 0.9fr 0.8fr;">
              <div>
                <div><strong>{{ d.title }}</strong></div>
                <div class="small">id: {{ d.id }}</div>
              </div>
              <div class="small">
                <input type="text" name="doc_path__{{ d.id }}" value="{{ d.path or '' }}">
              </div>
              <div>
                <select name="doc_category__{{ d.id }}">
                  {% for c in help_categories %}
                    <option value="{{ c.id }}" {{ 'selected' if d.category==c.id else '' }}>{{ c.label }}</option>
                  {% endfor %}
                </select>
              </div>
              <div>
                <label style="display:flex;align-items:center;gap:10px;justify-content:flex-end;">
                  <input type="checkbox" name="doc_enabled__{{ d.id }}" value="1" {{ 'checked' if d.enabled else '' }}>
                  <span>{{ 'ON' if d.enabled else 'OFF' }}</span>
                </label>
              </div>
            </div>
          {% endfor %}

          <div class="right" style="margin-top:14px;">
            <button class="tool-btn" type="submit" name="save" value="1">Save Help</button>
          </div>
        </form>
      </div>
    {% endif %}

  </div>
  {{ footer|safe }}
</body>
</html>
        """
        return render_template_string(
            tmpl,
            base_css=base_css,
            js=js,
            header=header,
            footer=footer,
            colors=colors,
            tab=tab,
            tools=tools,
            docs=docs,
            tool_categories=tool_categories,
            help_categories=help_categories,
        )

    @bp.route("/admin/tools/save", methods=["POST"])
    def save_tools():
        guard = _require_admin()
        if guard:
            return guard

        tools_cfg = get_tools_cfg() or {"tools": []}
        tools = tools_cfg.get("tools", []) if isinstance(tools_cfg, dict) else []

        # Apply checkbox+select values
        for t in tools:
            tid = t.get("id")
            if not tid:
                continue
            t["enabled"] = (request.form.get(f"tool_enabled__{tid}") == "1")
            t["category"] = (request.form.get(f"tool_category__{tid}") or t.get("category") or "misc").strip() or "misc"

        # Category bulk action
        cat_action = (request.form.get("cat_action") or "").strip()
        if ":" in cat_action:
            act, cat = cat_action.split(":", 1)
            act = act.strip().lower()
            cat = (cat or "").strip()
            if cat:
                for t in tools:
                    if (t.get("category") or "misc") == cat:
                        if act == "enable":
                            t["enabled"] = True
                        elif act == "disable":
                            t["enabled"] = False

        tools_cfg["tools"] = tools
        set_tools_cfg(tools_cfg)

        return redirect(url_for("admin.panel", tab="tools"))

    @bp.route("/admin/help/save", methods=["POST"])
    def save_help():
        guard = _require_admin()
        if guard:
            return guard

        help_cfg = get_help_cfg() or {"docs": []}
        docs = help_cfg.get("docs", []) if isinstance(help_cfg, dict) else []

        for d in docs:
            did = d.get("id")
            if not did:
                continue
            d["enabled"] = (request.form.get(f"doc_enabled__{did}") == "1")
            d["category"] = (request.form.get(f"doc_category__{did}") or d.get("category") or "misc").strip() or "misc"
            d["path"] = (request.form.get(f"doc_path__{did}") or d.get("path") or "").strip()

        cat_action = (request.form.get("cat_action") or "").strip()
        if ":" in cat_action:
            act, cat = cat_action.split(":", 1)
            act = act.strip().lower()
            cat = (cat or "").strip()
            if cat:
                for d in docs:
                    if (d.get("category") or "misc") == cat:
                        if act == "enable":
                            d["enabled"] = True
                        elif act == "disable":
                            d["enabled"] = False

        help_cfg["docs"] = docs
        set_help_cfg(help_cfg)

        return redirect(url_for("admin.panel", tab="help"))

    return bp
