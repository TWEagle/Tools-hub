from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint, current_app, render_template_string, request, redirect, url_for

from .layout import common_css, common_js, header_html, footer_html

bp = Blueprint("home", __name__)


HOME_TEMPLATE = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>{{ page_title }}</title>
  <style>
    {{ base_css|safe }}

    .tools-grid {
      display: grid;
      grid-template-columns: repeat({{ home_columns }}, minmax(280px, 1fr));
      gap: 18px;
      margin-top: 14px;
    }

    .tool-card {
      background: #111111;
      border-radius: 16px;
      padding: 16px 18px;
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

    .tool-card-link {
      display: block;
      text-decoration: none;
      color: inherit;
      cursor: pointer;
    }

    .tool-card h3 {
      margin: 0 0 8px 0;
      font-size: 1.1rem;
      color: var(--title);
      font-family: var(--font-btn);
    }

    .tool-card p {
      margin: 0 0 12px 0;
      color: var(--fg);
      font-size: 0.95rem;
      opacity: 0.95;
    }

    .tool-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 4px;
    }

    .tool-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 12px;
      border-radius: 999px;
      border: none;
      background: var(--btn-bg);
      color: var(--btn-fg);
      font-family: var(--font-btn);
      font-size: 0.86rem;
      cursor: pointer;
      text-decoration: none;
      border: 1px solid rgba(255,255,255,0.06);
    }

    .tool-btn:hover { filter: brightness(1.15); }

    .icon { font-size: 0.95rem; line-height: 1; }

    @media (max-width: 900px) {
      .tools-grid { grid-template-columns: 1fr; }
    }
  </style>
  <script>{{ common_js|safe }}</script>
</head>
<body>
  {{ header|safe }}
  <div class="page">
    <h1 style="margin: 16px 0 6px 0; font-family: var(--font-btn); color: var(--title);">{{ header_title }}</h1>
    <p class="muted">Tools worden ingelezen uit <code>config/tools.json</code>.</p>

    <div class="tools-grid">
      {% for tool in tools %}
        {% if tool.type == 'web' and tool.web_path %}
          <a href="{{ tool.web_path }}" class="tool-card tool-card-link">
            <h3>{{ tool.name }}</h3>
            <p>{{ tool.description }}</p>
            <div class="tool-actions">
              <span class="tool-btn"><span class="icon">{{ tool.icon_web or "🌐" }}</span>Open</span>
            </div>
          </a>
        {% else %}
          <div class="tool-card">
            <h3>{{ tool.name }}</h3>
            <p>{{ tool.description }}</p>
            <div class="tool-actions">
              {% if tool.type in ('web', 'web+gui') and tool.web_path %}
                <a class="tool-btn" href="{{ tool.web_path }}"><span class="icon">{{ tool.icon_web or "🌐" }}</span>Web</a>
              {% endif %}

              {% if tool.type in ('gui', 'web+gui') %}
                <form method="post" action="{{ url_for('home.start_tool') }}" style="margin:0;">
                  <input type="hidden" name="tool_id" value="{{ tool.id }}">
                  <button type="submit" class="tool-btn"><span class="icon">{{ tool.icon_gui or "🖥️" }}</span>GUI</button>
                </form>
              {% endif %}
            </div>
          </div>
        {% endif %}
      {% endfor %}
    </div>

    {{ footer|safe }}
  </div>
</body>
</html>
"""


def _find_tool(tools: List[Dict[str, Any]], tool_id: str) -> Optional[Dict[str, Any]]:
    for t in tools:
        if t.get("id") == tool_id:
            return t
    return None


@bp.get("/")
def index():
    st = current_app.config["HUB_STATE"]
    branding = st.branding
    settings = st.settings
    tools = st.tools

    home_columns = settings.get("home_columns", 3)
    try:
        home_columns = int(home_columns)
        home_columns = max(1, min(6, home_columns))
    except Exception:
        home_columns = 3

    base_css = common_css(settings)
    js = common_js()
    header = header_html(branding, settings, tools)
    footer = footer_html(branding)

    return render_template_string(
        HOME_TEMPLATE,
        page_title=branding.ui_value("window_title", branding.name),
        header_title=branding.ui_value("header_title", branding.name),
        base_css=base_css,
        common_js=js,
        header=header,
        footer=footer,
        tools=tools,
        home_columns=home_columns,
    )


@bp.post("/start/")
def start_tool():
    """
    GUI launching is optional — by default this calls the hub launcher hook in core.py.
    """
    st = current_app.config["HUB_STATE"]
    tools = st.tools
    tool_id = (request.form.get("tool_id") or "").strip()
    tool = _find_tool(tools, tool_id)
    if tool:
        launcher = current_app.config.get("GUI_LAUNCHER")
        if callable(launcher):
            launcher(tool)
    return redirect(url_for("home.index"))
