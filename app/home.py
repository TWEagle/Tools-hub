# app/home.py
from __future__ import annotations

from collections import defaultdict
from flask import Blueprint, render_template_string, url_for

from .layout import common_css, common_js, header_html, footer_html


def _enabled_default(it: dict) -> bool:
    return bool(it.get("enabled", True))


def create_home_blueprint(get_settings, get_branding, get_tools_cfg) -> Blueprint:
    bp = Blueprint("home", __name__)

    @bp.route("/")
    def index():
        settings = get_settings()
        branding = get_branding()
        tools_cfg = get_tools_cfg() or {}
        tools = tools_cfg.get("tools", []) if isinstance(tools_cfg, dict) else []

        # normal UI: only enabled
        visible = []
        for t in tools:
            if not _enabled_default(t):
                continue
            visible.append(t)

        # group by category
        grouped = defaultdict(list)
        for t in visible:
            cat = (t.get("category") or "misc").strip() or "misc"
            grouped[cat].append(t)

        # category labels if present
        cats = tools_cfg.get("categories")
        cat_label = {}
        if isinstance(cats, list):
            for c in cats:
                if isinstance(c, dict) and c.get("id"):
                    cat_label[str(c["id"])] = str(c.get("label") or c["id"]).strip()
        # fallback label
        for c in grouped.keys():
            cat_label.setdefault(c, c.title())

        # stable order: by categories list if exists, else alpha
        ordered_cats = []
        if isinstance(cats, list) and cats:
            for c in cats:
                cid = (c.get("id") if isinstance(c, dict) else None)
                if cid in grouped:
                    ordered_cats.append(cid)
            # append any missing
            for c in sorted(grouped.keys()):
                if c not in ordered_cats:
                    ordered_cats.append(c)
        else:
            ordered_cats = sorted(grouped.keys())

        colors = settings.get("colors", {})
        ui = settings.get("ui", {})
        base_css = common_css(settings)
        js = common_js()

        header = header_html(settings, title=branding.get("app_title", "Centraal Portaal"), tools=visible)
        footer = footer_html()

        home_columns = settings.get("home_columns", 3)
        try:
            home_columns = int(home_columns)
            if home_columns < 1:
                home_columns = 1
            if home_columns > 6:
                home_columns = 6
        except Exception:
            home_columns = 3

        tmpl = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <style>
    {{ base_css|safe }}

    .tools-grid {
      display: grid;
      grid-template-columns: repeat({{ home_columns }}, minmax(280px, 1fr));
      gap: 18px;
    }

    .tool-card {
      background: #111111;
      border-radius: 16px;
      padding: 16px 20px;
      box-shadow: 0 18px 35px rgba(0, 0, 0, 0.9);
      border: 1px solid rgba(255, 255, 255, 0.03);
      transform: translateY(0) scale(1);
      transition: transform 0.18s ease-out, box-shadow 0.18s ease-out, border-color 0.18s ease-out, background 0.18s ease-out;
    }
    .tool-card:hover {
      transform: translateY(-6px) scale(1.01);
      box-shadow: 0 24px 45px rgba(0, 0, 0, 1);
      border-color: rgba(0, 247, 0, 0.35);
      background: #151515;
    }
    .tool-card-link { display:block; text-decoration:none; color:inherit; cursor:pointer; }
    .tool-card h3 { margin:0 0 8px 0; font-size:1.1rem; color: {{ colors.title }}; }
    .tool-card p { margin:0 0 12px 0; color: {{ colors.general_fg }}; font-size:0.95rem; }
    .tool-actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:4px; }

    .tool-btn {
      display:inline-flex; align-items:center; gap:6px;
      padding:6px 12px; border-radius:999px; border:none;
      background: {{ colors.button_bg }}; color: {{ colors.button_fg }};
      font-family: {{ ui.font_buttons }}; font-size:0.85rem;
      cursor:pointer; text-decoration:none;
    }
    .tool-btn:hover { filter: brightness(1.15); }
    .muted { color:#999; font-size:0.95rem; }

    .cat-title { margin: 22px 0 12px; font-size: 1.15rem; color: {{ colors.title }}; }
    @media (max-width: 768px) { .tools-grid { grid-template-columns: 1fr; } }
  </style>
  <script>{{ js|safe }}</script>
</head>
<body>
  {{ header|safe }}
  <div class="page">
    <h1>{{ title }}</h1>
    <p class="muted">Tools zijn gegroepeerd per categorie. Admin beheer via <code>/admin</code>.</p>

    {% for cat in ordered_cats %}
      <div class="cat-title">{{ cat_label[cat] }}</div>
      <div class="tools-grid">
        {% for tool in grouped[cat] %}
          {% if tool.type == 'web' and tool.web_path %}
            <a href="{{ tool.web_path }}" class="tool-card tool-card-link">
              <h3>{{ tool.name }}</h3>
              <p>{{ tool.description }}</p>
              <div class="tool-actions">
                <span class="tool-btn">
                  <span class="icon">{{ tool.icon_web or "🌐" }}</span>
                  <span>Open</span>
                </span>
              </div>
            </a>
          {% else %}
            <div class="tool-card">
              <h3>{{ tool.name }}</h3>
              <p>{{ tool.description }}</p>
              <div class="tool-actions">
                {% if tool.web_path %}
                  <a class="tool-btn" href="{{ tool.web_path }}">
                    <span class="icon">{{ tool.icon_web or "🌐" }}</span>
                    <span>Open</span>
                  </a>
                {% endif %}
              </div>
            </div>
          {% endif %}
        {% endfor %}
      </div>
    {% endfor %}
  </div>
  {{ footer|safe }}
</body>
</html>
        """
        return render_template_string(
            tmpl,
            title=branding.get("app_title", "Centraal Portaal"),
            base_css=base_css,
            js=js,
            header=header,
            footer=footer,
            colors=colors,
            ui=ui,
            home_columns=home_columns,
            grouped=grouped,
            ordered_cats=ordered_cats,
            cat_label=cat_label,
        )

    return bp
