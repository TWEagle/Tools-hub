# app/home.py
from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, render_template_string, request, session

from .layout import common_css, common_js, header_html, footer_html


def _is_admin() -> bool:
    if session.get("admin_ok") is True:
        return True
    if (request.cookies.get("admin_ok") or "").strip() == "1":
        return True
    return False


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


def _normalize_tool_categories(tools_cfg: Dict[str, Any], tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cats = tools_cfg.get("categories")
    out: List[Dict[str, Any]] = []
    seen = set()

    if isinstance(cats, list):
        for c in cats:
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
                }
            )

    for t in tools:
        cid = (t.get("category") or "misc").strip() or "misc"
        if cid in seen:
            continue
        seen.add(cid)
        out.append({"id": cid, "label": cid.title(), "color": "#00f700", "enabled": True})

    if "misc" not in seen:
        out.append({"id": "misc", "label": "Misc", "color": "#00f700", "enabled": True})

    return out


def create_home_blueprint(get_settings, get_branding, get_tools_cfg) -> Blueprint:
    bp = Blueprint("home", __name__)

    @bp.route("/", methods=["GET"])
    def index():
        settings = get_settings() or {}
        branding = get_branding() or {}
        tools_cfg = get_tools_cfg() or {"tools": []}

        admin = _is_admin()

        tools = tools_cfg.get("tools") or []
        if not isinstance(tools, list):
            tools = []

        # normalize
        for t in tools:
            if not isinstance(t, dict):
                continue
            t.setdefault("enabled", True)
            t.setdefault("category", "misc")
            t["category"] = (t.get("category") or "misc").strip() or "misc"
            t["enabled"] = bool(t.get("enabled", True))
            t.setdefault("name", t.get("id") or "tool")
            t.setdefault("description", "")
            t.setdefault("web_path", "")
            t.setdefault("icon_web", "🧩")

        cats = _normalize_tool_categories(tools_cfg, tools)

        def cat_enabled(cid: str) -> bool:
            for c in cats:
                if c["id"] == cid:
                    return bool(c.get("enabled", True))
            return True

        visible_tools: List[Dict[str, Any]] = []
        for t in tools:
            if not isinstance(t, dict):
                continue
            if not admin:
                if not bool(t.get("enabled", True)):
                    continue
                if not cat_enabled(t["category"]):
                    continue
            visible_tools.append(t)

        # map cat->color
        cat_color = {c["id"]: c["color"] for c in cats}

        # home columns: uit settings.json (of default 3)
        ui = settings.get("ui") if isinstance(settings, dict) else {}
        cols = _safe_int((ui or {}).get("home_columns", settings.get("home_columns", 3)), 3, 1, 6)

        base_css = common_css(settings)
        js = common_js()
        header = header_html(settings, branding, title=branding.get("app_title", "Centraal Portaal"), right_html="")
        footer = footer_html(branding)

        tmpl = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>{{ branding.get('app_title','Centraal Portaal') }}</title>
  <style>
    {{ base_css|safe }}

    .grid {
      display:grid;
      grid-template-columns: repeat({{ cols }}, minmax(280px, 1fr));
      gap: 18px;
      margin-top: 18px;
    }

    .card {
      position: relative;
      background:#0b0b0b;
      border:1px solid #202020;
      border-radius: 16px;
      padding: 14px 14px 12px 14px;
      box-shadow: 0 18px 35px rgba(0,0,0,0.9);
      transition: transform .15s ease, border-color .15s ease;
      overflow:hidden;
    }
    .card:hover { transform: translateY(-4px); border-color: rgba(0,247,0,0.25); }

    .accent {
      position:absolute; left:0; top:0; bottom:0;
      width: 6px;
      background: var(--cat-color);
      opacity: 0.95;
    }

    .topline { display:flex; align-items:center; gap:10px; }
    .icon { font-size: 1.6rem; }
    .name { font-weight:900; font-size: 1.05rem; margin:0; }
    .desc { opacity:0.78; margin-top:8px; font-size:0.95rem; min-height: 2.4em; }

    .actions { margin-top: 12px; display:flex; gap:10px; flex-wrap:wrap; }
    .btn {
      display:inline-block;
      padding: 8px 12px;
      border-radius: 12px;
      border: 1px solid #2a2a2a;
      background: #101010;
      text-decoration:none;
      color: inherit;
      font-weight: 800;
    }
    .btn:hover { border-color: rgba(0,247,0,0.25); }

    .pills { display:flex; gap:8px; flex-wrap:wrap; margin-top: 10px; }
    .pill { font-size:0.85rem; opacity:0.8; border:1px solid #222; background:#0f0f0f; padding:4px 10px; border-radius:999px; }
  </style>
  <script>{{ js|safe }}</script>
</head>
<body>
  {{ header|safe }}

  <div class="page">
    <h1>{{ branding.get("app_title","Centraal Portaal") }}</h1>
    <p class="muted">
      Tools overzicht.
      {% if admin %}<span class="pill">ADMIN VIEW</span>{% endif %}
    </p>

    <div class="grid">
      {% for t in tools %}
        <div class="card" style="--cat-color: {{ cat_color.get(t.category, '#00f700') }};">
          <div class="accent"></div>

          <div class="topline">
            <div class="icon">{{ t.icon_web }}</div>
            <div>
              <div class="name">{{ t.name }}</div>
              <div class="pills">
                <span class="pill">{{ t.category }}</span>
                {% if admin %}
                  <span class="pill">enabled={{ 'true' if t.enabled else 'false' }}</span>
                {% endif %}
              </div>
            </div>
          </div>

          <div class="desc">{{ t.description }}</div>

          <div class="actions">
            {% if t.web_path %}
              <a class="btn" href="{{ t.web_path }}">Open</a>
            {% endif %}
          </div>
        </div>
      {% endfor %}
    </div>

    {% if tools|length == 0 %}
      <div class="card" style="--cat-color:#00f700;margin-top:14px;">
        <div class="accent"></div>
        <h3>Geen tools zichtbaar</h3>
        <div class="desc">Zet tools/categorieën aan in Admin.</div>
        <div class="actions">
          <a class="btn" href="/admin">Admin</a>
        </div>
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
            branding=branding,
            tools=visible_tools,
            cols=cols,
            cat_color=cat_color,
            admin=admin,
        )

    return bp
