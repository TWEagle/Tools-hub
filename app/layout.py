from __future__ import annotations

from typing import Any, Dict, List, Optional
from flask import url_for
from . import branding


def common_js() -> str:
    # Used by pages to provide helper functions
    return """function cynitReloadApp() {
  fetch('/restart').then(()=>location.reload()).catch(()=>location.reload());
}
"""


def common_css(settings: Dict[str, Any]) -> str:
    colors = settings.get("colors", {}) if isinstance(settings, dict) else {}
    ui = settings.get("ui", {}) if isinstance(settings, dict) else {}

    bg = colors.get("background", "#000000")
    fg = colors.get("general_fg", "#00FA00")
    title = colors.get("title", "#00A2FF")
    btn_bg = colors.get("button_bg", "#111111")
    btn_fg = colors.get("button_fg", "#00B7C3")

    font_main = ui.get("font_main", "Consolas")
    font_buttons = ui.get("font_buttons", "Segoe UI")

    return f"""    :root {{
      --bg: {bg};
      --fg: {fg};
      --title: {title};
      --btn-bg: {btn_bg};
      --btn-fg: {btn_fg};
      --font-main: {font_main};
      --font-buttons: {font_buttons};
    }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font-family: var(--font-main);
    }}

    a {{ color: inherit; }}

    .topbar {{
      position: sticky;
      top: 0;
      z-index: 999;
      background: rgba(0,0,0,0.92);
      border-bottom: 1px solid rgba(255,255,255,0.06);
      padding: 10px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}

    .topbar-left {{
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }}

    .topbar-title {{
      font-family: var(--font-buttons);
      font-size: 1.05rem;
      color: var(--title);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .topbar-actions {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.08);
      background: var(--btn-bg);
      color: var(--btn-fg);
      cursor: pointer;
      text-decoration: none;
      font-family: var(--font-buttons);
      font-size: 0.9rem;
    }}
    .btn:hover {{
      filter: brightness(1.15);
    }}

    .page {{
      padding: 18px 18px 26px 18px;
      max-width: 1400px;
      margin: 0 auto;
    }}

    .muted {{
      color: #9aa0a6;
      font-family: var(--font-buttons);
    }}

    code {{
      background: rgba(255,255,255,0.06);
      padding: 1px 6px;
      border-radius: 6px;
    }}
    """


def header_html(settings: Dict[str, Any], tools: List[Dict[str, Any]] | None = None, title: str | None = None, right_html: str = "") -> str:
    paths = settings.get("paths", {}) if isinstance(settings, dict) else {}
    logo_path = paths.get("logo") or branding.asset_path("logo_web", "assets/logos/logo.png")

    app_title = title or branding.header_title()

    # Simple: logo + title + home + reload
    home_url = "/"
    return f"""    <div class="topbar">
      <div class="topbar-left">
        <img src="/{logo_path}" alt="logo" style="height:34px;border-radius:10px;">
        <div class="topbar-title">{app_title}</div>
      </div>
      <div class="topbar-actions">
        <a class="btn" href="{home_url}">🏠 Home</a>
        <button class="btn" onclick="cynitReloadApp()">🔄 Reload</button>
        {right_html}
      </div>
    </div>
    """


def footer_html() -> str:
    return """    <div style="padding:16px 18px;color:#666;font-family:Segoe UI;font-size:0.85rem;text-align:center;">
      <span>{branding.app_name()}</span>
    </div>
    """
