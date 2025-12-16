#!/usr/bin/env python3
"""
config_editor.py

Centrale Config Editor voor alles in config/:
- *.json (validatie + pretty print)
- *.md / *.txt (raw)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

from flask import Blueprint, render_template_string, request, make_response

from app import layout as cynit_layout
from app import theme as cynit_theme

BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"

bp = Blueprint("config_editor", __name__)

TEMPLATE = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>Config & Theme Editor</title>
  <style>
    {{ base_css|safe }}

    .config-select-row { margin-bottom: 12px; }

    select.config-select {
      width: 100%;
      padding: 6px 10px;
      border-radius: 6px;
      border: 1px solid #333;
      background: #111;
      color: {{ colors.general_fg }};
      font-family: {{ ui.font_main }};
    }

    textarea.config-editor {
      width: 100%;
      min-height: 460px;
      resize: vertical;
      padding: 10px;
      border-radius: 8px;
      border: 1px solid #333;
      background: #050505;
      color: {{ colors.general_fg }};
      font-family: Consolas, monospace;
      font-size: 0.9rem;
      line-height: 1.4;
      box-sizing: border-box;
    }

    .help-text {
      margin-top: 8px;
      font-size: 0.85rem;
      color: #999;
    }

    .flash {
      margin-bottom: 10px;
      padding: 8px 12px;
      border-radius: 6px;
      background: #112211;
      border: 1px solid #228822;
      color: #88ff88;
      font-size: 0.85rem;
    }

    .flash-error {
      background: #221111;
      border-color: #aa3333;
      color: #ff8888;
    }

    .toolbar {
      display:flex;
      gap:10px;
      align-items:center;
      justify-content:space-between;
      margin: 10px 0 12px 0;
      flex-wrap: wrap;
    }

    .btnrow {
      display:flex;
      gap:10px;
      flex-wrap: wrap;
      align-items:center;
    }

    .smallhint { opacity: 0.85; font-size: 0.85rem; }
  </style>
  <script>
    {{ common_js|safe }}
    function confirmReload() {
      return confirm("Opslaan + herladen? (alle modules lezen daarna de nieuwe config)");
    }
  </script>
</head>
<body>
  {{ header|safe }}
  <div class="page">
    <h1>Config & Theme Editor</h1>
    <p class="muted">
      Alles centraal beheren vanuit <code>config/</code>. JSON wordt gevalideerd en mooi opgeslagen.
    </p>

    {% for msg, category in flashes %}
      <div class="flash {% if category == 'error' %}flash-error{% endif %}">{{ msg }}</div>
    {% endfor %}

    <form method="post" action="{{ url_for('config_editor.edit') }}">
      <div class="config-select-row">
        <label for="filename"><strong>Kies bestand</strong></label><br>
        <select id="filename" name="filename" class="config-select" onchange="this.form.submit()">
          {% for f in files %}
            <option value="{{ f.id }}" {% if f.id == current_file %}selected{% endif %}>
              {{ f.label }}
            </option>
          {% endfor %}
        </select>
      </div>

      <div class="toolbar">
        <div class="smallhint">
          Tip: pas <code>settings.json</code> aan → alles (cert_viewer/useful_links/...) pakt dit automatisch op met <code>get_settings_live()</code>.
        </div>

        <div class="btnrow">
          <button type="submit" name="action" value="save" class="btn">Opslaan</button>
          <button type="submit" name="action" value="save_reload" class="btn" onclick="return confirmReload();">Opslaan + reload</button>
        </div>
      </div>

      <textarea name="content" class="config-editor">{{ content }}</textarea>

      <div class="help-text">
        JSON-bestanden worden gevalideerd en pretty opgeslagen. Markdown/tekst wordt raw bewaard.
      </div>
    </form>
  </div>
  {{ footer|safe }}
</body>
</html>
"""


def _list_config_files() -> List[Dict[str, str]]:
    files: List[Dict[str, str]] = []
    if not CONFIG_DIR.exists():
        return files

    for p in sorted(CONFIG_DIR.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".json", ".md", ".txt"}:
            continue
        files.append({"id": p.name, "label": f"{p.name} (config/{p.name})"})
    return files


def _safe_resolve_config_file(filename: str) -> Tuple[bool, Path, str]:
    """
    Voorkom path traversal.
    """
    filename = (filename or "").strip()
    if not filename:
        return False, CONFIG_DIR, "Geen bestandsnaam."

    # enkel basename toelaten
    if "/" in filename or "\\" in filename or ".." in filename:
        return False, CONFIG_DIR, "Ongeldige bestandsnaam."

    p = (CONFIG_DIR / filename).resolve()
    if CONFIG_DIR.resolve() not in p.parents:
        return False, CONFIG_DIR, "Ongeldig pad."
    return True, p, ""


def _read_file(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except Exception:
        text = path.read_text(errors="ignore")

    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
            return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception:
            return text
    return text


def _write_file(path: Path, content: str) -> str | None:
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(content)
        except Exception as exc:
            return f"JSON is niet geldig: {exc}"
        try:
            pretty = json.dumps(data, indent=2, ensure_ascii=False)
            path.write_text(pretty, encoding="utf-8")
        except Exception as exc:
            return f"Kon JSON niet opslaan: {exc}"
    else:
        try:
            path.write_text(content, encoding="utf-8")
        except Exception as exc:
            return f"Kon bestand niet opslaan: {exc}"
    return None


@bp.route("/config-editor", methods=["GET", "POST"])
def edit():
    # ✅ LIVE ctx
    settings = cynit_theme.get_settings_live()
    tools = cynit_theme.get_tools_list_live()

    colors = settings.get("colors", {})
    ui = settings.get("ui", {})

    base_css = cynit_layout.common_css(settings)
    common_js = cynit_layout.common_js()

    header_html = cynit_layout.header_html(
        settings,
        tools=tools,
        title="Config & Theme Editor",
        right_html="",
    )
    footer_html = cynit_layout.footer_html()

    files = _list_config_files()
    if not files:
        return make_response("Geen config-bestanden gevonden in config/.", 404)

    if request.method == "POST":
        current_file = request.form.get("filename") or files[0]["id"]
    else:
        current_file = request.args.get("filename") or files[0]["id"]

    ok, current_path, err = _safe_resolve_config_file(current_file)
    if not ok:
        return make_response(err, 400)

    flashes: List[tuple[str, str]] = []

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action in ("save", "save_reload"):
            content = request.form.get("content", "")
            error = _write_file(current_path, content)
            if error:
                flashes.append((error, "error"))
            else:
                flashes.append((f"{current_file} opgeslagen.", "ok"))

            # forceer live caches te refreshen na edits aan settings/tools
            if current_file == "settings.json":
                cynit_theme.get_settings_live()  # cache herbouwt zichzelf via mtime
            if current_file == "tools.json":
                cynit_theme.get_tools_live()

    content = _read_file(current_path)

    # save_reload: je kan hier eventueel /restart gebruiken als je dat hebt in hub
    # maar meestal is het niet meer nodig als al je modules live settings lezen.

    return render_template_string(
        TEMPLATE,
        base_css=base_css,
        common_js=common_js,
        header=header_html,
        footer=footer_html,
        colors=colors,
        ui=ui,
        files=files,
        current_file=current_file,
        content=content,
        flashes=flashes,
    )


def register_web_routes(app, settings=None, tools=None):
    # settings/tools worden genegeerd → we lezen live in de route zelf
    app.register_blueprint(bp)
