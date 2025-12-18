# app/admin.py
from __future__ import annotations

from typing import Any, Dict, List

from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    session,
    render_template_string,
    make_response,
)

from .layout import common_css, header_html, footer_html, common_js


PIN_DEFAULT = "3990"


def _safe_int(v: Any, default: int, lo: int = 1, hi: int = 6) -> int:
    try:
        x = int(v)
        if x < lo:
            return lo
        if x > hi:
            return hi
        return x
    except Exception:
        return default


def _enabled_default(it: dict) -> bool:
    return bool(it.get("enabled", True))


def _normalize_categories(items: List[dict], categories: Any) -> List[Dict[str, Any]]:
    """
    categories[] = {id,label,color,enabled,columns}
    Als ontbreekt: bouw uit items.category
    """
    out: List[Dict[str, Any]] = []
    seen = set()

    if isinstance(categories, list):
        for c in categories:
            if not isinstance(c, dict):
                continue
            cid = (c.get("id") or "").strip() or "misc"
            if cid in seen:
                continue
            seen.add(cid)
            out.append(
                {
                    "id": cid,
                    "label": (c.get("label") or cid.title()).strip(),
                    "color": (c.get("color") or "#00f700").strip(),
                    "enabled": bool(c.get("enabled", True)),
                    "columns": _safe_int(c.get("columns", 3), 3, 1, 6),
                }
            )

    for it in items:
        if not isinstance(it, dict):
            continue
        cid = (it.get("category") or "misc").strip() or "misc"
        if cid in seen:
            continue
        seen.add(cid)
        out.append({"id": cid, "label": cid.title(), "color": "#00f700", "enabled": True, "columns": 3})

    if "misc" not in seen:
        out.append({"id": "misc", "label": "Misc", "color": "#00f700", "enabled": True, "columns": 3})

    return out


def create_admin_blueprint(
    base_dir,
    get_settings,
    get_branding,
    get_tools_cfg,
    set_tools_cfg,
    get_help_cfg,
    set_help_cfg,
) -> Blueprint:
    bp = Blueprint("admin", __name__)

    def _is_admin() -> bool:
        if session.get("admin_ok") is True:
            return True
        if (request.cookies.get("admin_ok") or "").strip() == "1":
            return True
        return False

    def _require_admin():
        if not _is_admin():
            return redirect(url_for("admin.login", next=request.path))
        return None

    def _get_pin() -> str:
        settings = get_settings() or {}
        branding = get_branding() or {}
        pin = None

        sec = settings.get("secrets") if isinstance(settings, dict) else None
        if isinstance(sec, dict):
            pin = sec.get("admin_pin") or sec.get("yt_pin")

        if not pin:
            bsec = branding.get("secrets") if isinstance(branding, dict) else None
            if isinstance(bsec, dict):
                pin = bsec.get("admin_pin")

        return str(pin or PIN_DEFAULT).strip()

    @bp.route("/admin/login", methods=["GET", "POST"])
    def login():
        settings = get_settings() or {}
        branding = get_branding() or {}

        base_css = common_css(settings)
        js = common_js()
        header = header_html(settings, branding, title="Admin login", right_html="")
        footer = footer_html(branding)

        next_url = request.args.get("next") or url_for("admin.panel")
        err = None

        if request.method == "POST":
            pin = (request.form.get("pin") or "").strip()
            if pin == _get_pin():
                session["admin_ok"] = True
                session.permanent = True  # => session cookie blijft (afhankelijk van browser settings)

                resp = make_response(redirect(next_url))
                # extra expliciete cookie (niet “secure”, maar handig + wat jij vroeg)
                resp.set_cookie("admin_ok", "1", max_age=60 * 60 * 24 * 30, samesite="Lax")
                return resp

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
    <p class="muted">PIN is nodig om tools/help te beheren.</p>

    {% if err %}<div class="flash-err">{{ err }}</div>{% endif %}

    <form method="post">
      <label><strong>PIN</strong></label>
      <input name="pin" type="password" autofocus
             style="width:100%;padding:10px;border-radius:10px;border:1px solid #333;background:#0b0b0b;color:inherit;font-size:1.1rem;letter-spacing:3px;text-align:center;">
      <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap;">
        <button class="tool-btn" type="submit">Login</button>
        <a class="tool-btn" href="{{ url_for('home.index') }}">Terug</a>
      </div>
    </form>
  </div>
  {{ footer|safe }}
</body>
</html>
        """
        return render_template_string(tmpl, base_css=base_css, js=js, header=header, footer=footer, err=err)

    @bp.route("/admin/logout")
    def logout():
        session.pop("admin_ok", None)
        resp = make_response(redirect(url_for("home.index")))
        resp.delete_cookie("admin_ok")
        return resp

    @bp.route("/admin", methods=["GET"])
    def panel():
        guard = _require_admin()
        if guard:
            return guard

        settings = get_settings() or {}
        branding = get_branding() or {}

        base_css = common_css(settings)
        js = common_js()
        header = header_html(settings, branding, title="Admin panel", right_html="")
        footer = footer_html(branding)

        tools_cfg = get_tools_cfg() or {"tools": []}
        help_cfg = get_help_cfg() or {"docs": []}

        tools = tools_cfg.get("tools") or []
        docs = help_cfg.get("docs") or []

        # normalize
        for t in tools:
            if not isinstance(t, dict):
                continue
            t.setdefault("enabled", True)
            t["enabled"] = _enabled_default(t)
            t.setdefault("category", "misc")
            t["category"] = (t.get("category") or "misc").strip() or "misc"

        for d in docs:
            if not isinstance(d, dict):
                continue
            d.setdefault("enabled", True)
            d["enabled"] = _enabled_default(d)
            d.setdefault("category", "misc")
            d["category"] = (d.get("category") or "misc").strip() or "misc"
            d.setdefault("title", d.get("title") or d.get("name") or d.get("id") or "doc")

        tool_categories = _normalize_categories(tools, tools_cfg.get("categories"))
        help_categories = _normalize_categories(docs, help_cfg.get("categories"))

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

    .tabs { display:flex; gap:10px; margin: 10px 0 18px 0; flex-wrap:wrap; }
    .tab {
      padding: 8px 14px; border-radius: 999px; border: 1px solid #333;
      background: #0b0b0b; color: inherit;
      cursor: pointer; text-decoration:none; font-weight:800;
    }
    .tab.active { border-color: rgba(0,247,0,0.35); background:#121212; }

    .panel { background:#0a0a0a;border:1px solid #222;border-radius:16px;padding:14px; }
    .row { display:grid; grid-template-columns: 1.1fr 1.6fr 0.9fr 0.8fr; gap:10px; align-items:center; padding:8px 0; border-bottom:1px solid #141414; }
    .row:last-child { border-bottom:none; }
    .small { font-size:0.9rem; color:#aaa; }
    input[type="text"] { width:100%; padding:8px 10px; border-radius:10px; border:1px solid #333; background:#0b0b0b; color: inherit; }
    select { width:100%; padding:8px 10px; border-radius:10px; border:1px solid #333; background:#0b0b0b; color: inherit; }
    .right { display:flex; gap:10px; justify-content:flex-end; flex-wrap:wrap; }

    .catbar { display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 12px; }
    .catpill {
      display:flex; align-items:center; gap:10px;
      padding:6px 10px; border-radius:999px; border:1px solid #333; background:#0b0b0b;
      font-size:0.9rem;
    }
    .dot { width:10px; height:10px; border-radius:999px; background: var(--c); }
    .tool-btn { margin:0; }

    .cat-editor {
      display:grid;
      grid-template-columns: 1.2fr 1fr 0.8fr 0.7fr 1.2fr;
      gap:10px; align-items:center;
      padding:10px 0; border-bottom:1px solid #141414;
    }
    .cat-editor:last-child { border-bottom:none; }
    .mini { font-size:0.85rem; opacity:0.8; }
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
    <p class="muted">Beheer zichtbaarheid + categorieën (kleur/columns) voor Tools en Help.</p>

    <div class="tabs">
      <a class="tab {{ 'active' if tab=='tools' else '' }}" href="{{ url_for('admin.panel', tab='tools') }}">Tools</a>
      <a class="tab {{ 'active' if tab=='help' else '' }}" href="{{ url_for('admin.panel', tab='help') }}">Help</a>
    </div>

    {% if tab == 'tools' %}
      <div class="panel">
        <h2>Tool categories</h2>
        <p class="small">Categorie properties: <strong>enabled</strong>, <strong>color</strong>, <strong>columns</strong>.</p>

        <form method="post" action="{{ url_for('admin.save_tool_categories') }}">
          {% for c in tool_categories %}
            <div class="cat-editor" style="--c: {{ c.color }};">
              <div style="display:flex;align-items:center;gap:10px;">
                <div class="dot"></div>
                <div>
                  <div><strong>{{ c.id }}</strong></div>
                  <div class="mini">label in UI</div>
                </div>
              </div>
              <input type="text" name="cat_label__{{ c.id }}" value="{{ c.label }}">
              <input type="text" name="cat_color__{{ c.id }}" value="{{ c.color }}">
              <select name="cat_cols__{{ c.id }}">
                {% for n in range(1,7) %}
                  <option value="{{ n }}" {{ 'selected' if c.columns==n else '' }}>{{ n }} cols</option>
                {% endfor %}
              </select>
              <label style="display:flex;align-items:center;gap:10px;justify-content:flex-end;">
                <input type="checkbox" name="cat_enabled__{{ c.id }}" value="1" {{ 'checked' if c.enabled else '' }}>
                <span>{{ 'ON' if c.enabled else 'OFF' }}</span>
              </label>
            </div>
          {% endfor %}
          <div class="right" style="margin-top:14px;">
            <button class="tool-btn" type="submit">Save categories</button>
          </div>
        </form>

        <hr style="border:none;border-top:1px solid #1b1b1b; margin: 16px 0;">

        <h2>Tools</h2>
        <p class="small">Toggle <strong>enabled</strong> en pas <strong>category</strong> aan. Save schrijft naar <code>config/tools.json</code>.</p>

        <form method="post" action="{{ url_for('admin.save_tools') }}">
          <div class="catbar">
            {% for c in tool_categories %}
              <span class="catpill" style="--c: {{ c.color }};">
                <span class="dot"></span>
                <span>{{ c.label }}</span>
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
        <h2>Help categories</h2>
        <p class="small">Categorie properties: <strong>enabled</strong>, <strong>color</strong>, <strong>columns</strong>.</p>

        <form method="post" action="{{ url_for('admin.save_help_categories') }}">
          {% for c in help_categories %}
            <div class="cat-editor" style="--c: {{ c.color }};">
              <div style="display:flex;align-items:center;gap:10px;">
                <div class="dot"></div>
                <div>
                  <div><strong>{{ c.id }}</strong></div>
                  <div class="mini">label in UI</div>
                </div>
              </div>
              <input type="text" name="cat_label__{{ c.id }}" value="{{ c.label }}">
              <input type="text" name="cat_color__{{ c.id }}" value="{{ c.color }}">
              <select name="cat_cols__{{ c.id }}">
                {% for n in range(1,7) %}
                  <option value="{{ n }}" {{ 'selected' if c.columns==n else '' }}>{{ n }} cols</option>
                {% endfor %}
              </select>
              <label style="display:flex;align-items:center;gap:10px;justify-content:flex-end;">
                <input type="checkbox" name="cat_enabled__{{ c.id }}" value="1" {{ 'checked' if c.enabled else '' }}>
                <span>{{ 'ON' if c.enabled else 'OFF' }}</span>
              </label>
            </div>
          {% endfor %}
          <div class="right" style="margin-top:14px;">
            <button class="tool-btn" type="submit">Save categories</button>
          </div>
        </form>

        <hr style="border:none;border-top:1px solid #1b1b1b; margin: 16px 0;">

        <h2>Help docs</h2>
        <p class="small">Save schrijft naar <code>config/help.json</code>.</p>

        <form method="post" action="{{ url_for('admin.save_help') }}">
          <div class="catbar">
            {% for c in help_categories %}
              <span class="catpill" style="--c: {{ c.color }};">
                <span class="dot"></span>
                <span>{{ c.label }}</span>
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
        tools = tools_cfg.get("tools") or []

        for t in tools:
            tid = (t.get("id") or "").strip()
            if not tid:
                continue
            t["enabled"] = (request.form.get(f"tool_enabled__{tid}") == "1")
            t["category"] = (request.form.get(f"tool_category__{tid}") or t.get("category") or "misc").strip() or "misc"

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

    @bp.route("/admin/tools/categories/save", methods=["POST"])
    def save_tool_categories():
        guard = _require_admin()
        if guard:
            return guard

        tools_cfg = get_tools_cfg() or {"tools": []}
        tools = tools_cfg.get("tools") or []
        cats = _normalize_categories(tools, tools_cfg.get("categories"))

        for c in cats:
            cid = c["id"]
            c["label"] = (request.form.get(f"cat_label__{cid}") or c["label"]).strip() or cid.title()
            c["color"] = (request.form.get(f"cat_color__{cid}") or c["color"]).strip() or "#00f700"
            c["columns"] = _safe_int(request.form.get(f"cat_cols__{cid}"), c["columns"], 1, 6)
            c["enabled"] = (request.form.get(f"cat_enabled__{cid}") == "1")

        tools_cfg["categories"] = cats
        set_tools_cfg(tools_cfg)
        return redirect(url_for("admin.panel", tab="tools"))

    @bp.route("/admin/help/save", methods=["POST"])
    def save_help():
        guard = _require_admin()
        if guard:
            return guard

        help_cfg = get_help_cfg() or {"docs": []}
        docs = help_cfg.get("docs") or []

        for d in docs:
            did = (d.get("id") or "").strip()
            if not did:
                continue
            d["enabled"] = (request.form.get(f"doc_enabled__{did}") == "1")
            d["category"] = (request.form.get(f"doc_category__{did}") or d.get("category") or "misc").strip() or "misc"
            d["path"] = (request.form.get(f"doc_path__{did}") or d.get("path") or "").strip()
            d["title"] = (d.get("title") or d.get("name") or did).strip()

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

    @bp.route("/admin/help/categories/save", methods=["POST"])
    def save_help_categories():
        guard = _require_admin()
        if guard:
            return guard

        help_cfg = get_help_cfg() or {"docs": []}
        docs = help_cfg.get("docs") or []
        cats = _normalize_categories(docs, help_cfg.get("categories"))

        for c in cats:
            cid = c["id"]
            c["label"] = (request.form.get(f"cat_label__{cid}") or c["label"]).strip() or cid.title()
            c["color"] = (request.form.get(f"cat_color__{cid}") or c["color"]).strip() or "#00f700"
            c["columns"] = _safe_int(request.form.get(f"cat_cols__{cid}"), c["columns"], 1, 6)
            c["enabled"] = (request.form.get(f"cat_enabled__{cid}") == "1")

        help_cfg["categories"] = cats
        set_help_cfg(help_cfg)
        return redirect(url_for("admin.panel", tab="help"))

    return bp
