from __future__ import annotations

from typing import Any, Dict, List, Optional

from .branding import Branding


def common_css(settings: Dict[str, Any]) -> str:
    colors = settings.get("colors", {}) if isinstance(settings, dict) else {}
    ui = settings.get("ui", {}) if isinstance(settings, dict) else {}

    bg = colors.get("background", "#000")
    fg = colors.get("general_fg", "#0f0")
    title = colors.get("title", "#0af")
    btn_bg = colors.get("button_bg", "#111")
    btn_fg = colors.get("button_fg", "#0ff")
    font_main = ui.get("font_main", "Consolas")
    font_btn = ui.get("font_buttons", "Segoe UI")

    return f"""
    :root {{
      --bg: {bg};
      --fg: {fg};
      --title: {title};
      --btn-bg: {btn_bg};
      --btn-fg: {btn_fg};
      --font-main: {font_main};
      --font-btn: {font_btn};
    }}

    html, body {{
      background: var(--bg);
      color: var(--fg);
      margin: 0;
      font-family: var(--font-main);
    }}

    .page {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 18px 18px 40px 18px;
    }}

    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 18px;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      background: rgba(0,0,0,0.55);
      position: sticky;
      top: 0;
      backdrop-filter: blur(6px);
      z-index: 10;
    }}

    .brand {{
      display:flex;
      align-items:center;
      gap: 12px;
      min-width: 240px;
    }}

    .brand img {{
      max-height: 44px;
      border-radius: 10px;
      box-shadow: 0 10px 22px rgba(0,0,0,0.75);
    }}

    .brand-title {{
      font-family: var(--font-btn);
      font-weight: 700;
      font-size: 1.05rem;
      color: var(--title);
      letter-spacing: 0.3px;
    }}

    .nav {{
      display:flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}

    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 14px;
      border-radius: 999px;
      background: var(--btn-bg);
      color: var(--btn-fg);
      text-decoration: none;
      font-family: var(--font-btn);
      font-size: 0.9rem;
      border: 1px solid rgba(255,255,255,0.06);
      cursor: pointer;
      user-select: none;
    }}

    .btn:hover {{
      filter: brightness(1.15);
    }}

    .muted {{
      color: rgba(255,255,255,0.55);
      font-family: var(--font-btn);
    }}

    footer {{
      margin-top: 30px;
      padding-top: 14px;
      border-top: 1px solid rgba(255,255,255,0.06);
      color: rgba(255,255,255,0.50);
      font-family: var(--font-btn);
      font-size: 0.85rem;
    }}

    code {{
      color: rgba(255,255,255,0.85);
    }}
    """


def common_js() -> str:
    return """
    function cynitReload() {
      fetch('/restart').then(() => location.reload()).catch(() => location.reload());
    }
    """


def header_html(branding: Branding, settings: Dict[str, Any], tools: List[Dict[str, Any]], right_html: str = "") -> str:
    """
    Minimal topbar header, brand-agnostic via branding.json.
    """
    title = branding.ui_value("header_title", branding.name)
    logo = branding.asset_path("logo") or settings.get("paths", {}).get("logo", "")

    # If logo is relative, we serve it via /assets route in core.py
    # So we link to /assets/<path>
    logo_url = f"/assets/{logo.lstrip('/')}" if logo else ""

    # Optional quick links (only web tools with web_path)
    nav_links = []
    for t in tools or []:
        if t.get("type") in ("web", "web+gui") and t.get("web_path"):
            nav_links.append((t.get("name") or t.get("id") or "tool", t["web_path"]))

    nav_html = "".join([f'<a class="btn" href="{href}">🌐 {name}</a>' for name, href in nav_links[:6]])

    return f"""
    <div class="topbar">
      <div class="brand">
        {f'<img src="{logo_url}" alt="logo">' if logo_url else ''}
        <div class="brand-title">{title}</div>
      </div>
      <div class="nav">
        {nav_html}
        <a class="btn" href="#" onclick="cynitReload();return false;">🔄 Reload</a>
        {right_html or ""}
      </div>
    </div>
    """


def footer_html(branding: Branding) -> str:
    txt = branding.ui_value("footer_text", branding.copyright)
    return f"<footer>{txt}</footer>"
