from __future__ import annotations

from typing import Any, Dict, List
from flask import render_template_string
from . import layout, branding

HOME_TEMPLATE = """<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>{{ window_title }}</title>
  <style>
  {{ base_css|safe }}

  .tools-grid {
    display: grid;
    grid-template-columns: repeat({{ home_columns }}, minmax(280px, 1fr));
    gap: 20px;
    margin-top: 14px;
  }

  .tool-card {
    background: #111111;
    border-radius: 16px;
    padding: 16px 20px;
    box-shadow: 0 18px 35px rgba(0, 0, 0, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.03);
    transform: translateY(0) scale(1);
    transition:
      transform 0.18s ease-out,
      box-shadow 0.18s ease-out,
      border-color 0.18s ease-out,
      background 0.18s ease-out;
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
    color: {{ colors.title }};
    font-family: {{ ui.font_buttons }};
  }

  .tool-card p {
    margin: 0 0 12px 0;
    color: {{ colors.general_fg }};
    font-size: 0.95rem;
    font-family: {{ ui.font_buttons }};
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
    padding: 6px 12px;
    border-radius: 999px;
    border: none;
    background: {{ colors.button_bg }};
    color: {{ colors.button_fg }};
    font-family: {{ ui.font_buttons }};
    font-size: 0.85rem;
    cursor: pointer;
    text-decoration: none;
  }

  .tool-btn:hover { filter: brightness(1.15); }

  @media (max-width: 768px) {
    .tools-grid { grid-template-columns: 1fr; }
  }
  </style>
  <script>
  {{ common_js|safe }}
  </script>
</head>
<body>
  {{ header|safe }}
  <div class="page">
    <h1 style="margin-top:0;">{{ header_title }}</h1>
    <p class="muted">
      Deze pagina leest automatisch je tools uit <code>config/tools.json</code>.
    </p>

    <h2>Tools</h2>

    <div class="tools-grid">
      {% for tool in tools %}
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
              {% if tool.type == 'web+gui' and tool.web_path %}
                <a class="tool-btn" href="{{ tool.web_path }}">
                  <span class="icon">{{ tool.icon_web or "🌐" }}</span>
                  <span>Open</span>
                </a>
              {% endif %}

              {% if tool.type in ('gui','web+gui') %}
                <form method="post" action="/start/" style="margin:0;">
                  <input type="hidden" name="tool_id" value="{{ tool.id }}">
                  <button type="submit" class="tool-btn">
                    <span class="icon">{{ tool.icon_gui or "🖥️" }}</span>
                    <span>Start</span>
                  </button>
                </form>
              {% endif %}
            </div>
          </div>
        {% endif %}
      {% endfor %}
    </div>
  </div>
  {{ footer|safe }}
</body>
</html>
"""


def render_home(*, tools: List[Dict[str, Any]], settings: Dict[str, Any], dev_mode: bool) -> str:
    colors = settings.get("colors", {})
    ui = settings.get("ui", {})

    # home_columns
    home_columns = settings.get("home_columns", 3)
    try:
        home_columns = int(home_columns)
        home_columns = max(1, min(7, home_columns))
    except Exception:
        home_columns = 3

    base_css = layout.common_css(settings)
    common_js = layout.common_js()
    header_html = layout.header_html(settings, tools=tools, title=branding.header_title(), right_html="")
    footer_html = layout.footer_html()

    return render_template_string(
        HOME_TEMPLATE,
        tools=tools,
        colors=colors,
        ui=ui,
        base_css=base_css,
        common_js=common_js,
        header=header_html,
        footer=footer_html,
        home_columns=home_columns,
        dev_mode=dev_mode,
        window_title=branding.window_title(),
        header_title=branding.header_title(),
    )
