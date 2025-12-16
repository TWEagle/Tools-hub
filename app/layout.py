# app/layout.py
from __future__ import annotations

from datetime import datetime


def common_css(settings: dict) -> str:
    colors = settings.get("colors", {}) if isinstance(settings, dict) else {}
    ui = settings.get("ui", {}) if isinstance(settings, dict) else {}

    bg = colors.get("background", "#000000")
    fg = colors.get("general_fg", "#00FA00")
    btn_bg = colors.get("button_bg", "#111111")
    btn_fg = colors.get("button_fg", "#00B7C3")

    font_main = ui.get("font_main", "Consolas")
    font_buttons = ui.get("font_buttons", "Segoe UI")

    return f"""
    body {{
      margin:0;
      background:{bg};
      color:{fg};
      font-family:{font_main}, system-ui, -apple-system, Segoe UI, Arial;
    }}
    .page {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 18px 18px 40px;
    }}
    a {{ color: inherit; }}
    code {{
      background:#0b0b0b;
      border:1px solid #222;
      padding:2px 6px;
      border-radius:8px;
      color:{fg};
    }}
    .tool-btn {{
      display:inline-flex; align-items:center; gap:8px;
      padding:8px 14px; border-radius:999px; border:none;
      background:{btn_bg}; color:{btn_fg};
      font-family:{font_buttons}, system-ui;
      cursor:pointer; text-decoration:none;
    }}
    .tool-btn:hover {{ filter: brightness(1.15); }}
    .muted {{ color:#999; }}
    """


def common_js() -> str:
    return ""

def header_html(settings: dict, title: str, tools: list[dict]) -> str:
    return f"""
    <div style="border-bottom:1px solid #111; padding: 14px 18px; background:#050505;">
      <div style="max-width:1200px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:12px;">
        <div style="font-weight:800; letter-spacing:0.3px;">{title}</div>
        <div style="display:flex; gap:10px; align-items:center;">
          <a class="tool-btn" href="/">Home</a>
          <a class="tool-btn" href="/help">Help</a>
          <a class="tool-btn" href="/admin">Admin</a>
        </div>
      </div>
    </div>
    """


def footer_html() -> str:
    year = datetime.now().year
    return f"""
    <div style="border-top:1px solid #111; padding: 14px 18px; background:#050505;">
      <div style="max-width:1200px;margin:0 auto; color:#777; font-size:0.9rem;">
        © CyNiT 2024-2026
      </div>
    </div>
    """
