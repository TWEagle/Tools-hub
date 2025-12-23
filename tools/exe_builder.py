#!/usr/bin/env python3
"""
tools/exe_builder.py  (Tools Hub)

Brand-agnostic EXE + bundle builder (web tool).

Route:
- /exe-builder  (GET/POST)

Wat doet dit:
- Optioneel: upload logo (PNG) -> maakt ICO
- Bouwt een standalone EXE via PyInstaller (default entrypoint: run.py in repo root)
- Optioneel: maakt een ZIP bundel van de build-output

Opzet:
- core.py registreert blueprint:
    from tools.exe_builder import create_blueprint
    app.register_blueprint(create_blueprint(get_settings, get_branding, get_tools_cfg))

Vereisten:
- pyinstaller (in venv)
- pillow (voor PNG->ICO)  (optioneel, maar aanbevolen)
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, Response, make_response, redirect, render_template_string, request, send_file, url_for, session

# ---- optional layout helpers (from app/) ----
try:
    from app.layout import common_css, header_html, footer_html, common_js
except Exception:  # pragma: no cover
    def common_css(settings: dict) -> str:
        return "body{font-family:Arial,sans-serif;background:#0b0b0b;color:#ddd;margin:0}.page{padding:20px}"
    def header_html(settings: dict, title: str, tools: list | None = None, right_html: str = "") -> str:
        return f"<div style='padding:12px 16px;border-bottom:1px solid #222;background:#111'><b>{title}</b></div>"
    def footer_html(settings: dict) -> str:
        return "<div style='padding:10px 16px;border-top:1px solid #222;background:#111;text-align:right;font-size:.9em'>© CyNiT 2024 - 2026</div>"
    def common_js() -> str:
        return ""

# ---- optional exports helpers ----
try:
    from app.exports import send_zip_download, zip_from_folder
except Exception:  # pragma: no cover
    send_zip_download = None
    zip_from_folder = None


# -----------------------------
# helpers
# -----------------------------
def _repo_root() -> Path:
    # tools/xxx.py -> repo root is parents[1]
    return Path(__file__).resolve().parents[1]


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _safe_name(name: str, default: str = "ToolsHub") -> str:
    name = (name or "").strip() or default
    allowed = []
    for ch in name:
        if ch.isalnum() or ch in ("-", "_", "."):
            allowed.append(ch)
        else:
            allowed.append("_")
    out = "".join(allowed).strip("._-")
    return out or default


def _get_title(branding: dict, fallback: str) -> str:
    titles = branding.get("titles", {}) if isinstance(branding, dict) else {}
    if isinstance(titles, dict):
        return str(titles.get("exe_builder") or branding.get("app_title") or fallback)
    return str(branding.get("app_title") or fallback)


def _get_tools_list(get_tools_cfg) -> list:
    tools_cfg = get_tools_cfg() or {"tools": []}
    tools = tools_cfg.get("tools", []) if isinstance(tools_cfg, dict) else []
    return tools if isinstance(tools, list) else []


def _png_to_ico_bytes(png_bytes: bytes, sizes: Tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)) -> bytes:
    try:
        from PIL import Image
    except Exception as e:
        raise RuntimeError("Pillow ontbreekt: installeer 'pillow' in je venv.") from e

    im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    out = io.BytesIO()
    im.save(out, format="ICO", sizes=[(s, s) for s in sizes])
    return out.getvalue()


def _run(cmd: List[str], cwd: Path, log_lines: List[str], env: Optional[dict] = None) -> int:
    log_lines.append(f"$ {' '.join(cmd)}")
    try:
        p = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        assert p.stdout is not None
        for line in p.stdout:
            log_lines.append(line.rstrip("\n"))
        return int(p.wait())
    except Exception as e:
        log_lines.append(f"[ERROR] {e}")
        return 1


def _pyinstaller_add_data(src: Path, dest: str) -> str:
    # Windows separator is ';' in --add-data "SRC;DEST"
    return f"{str(src)};{dest}"


@dataclass
class BuildResult:
    ok: bool
    out_dir: Path
    exe_path: Optional[Path]
    zip_path: Optional[Path]
    log_text: str


# -----------------------------
# builder
# -----------------------------
def build_exe(
    base_dir: Path,
    app_name: str,
    icon_ico_path: Optional[Path],
    include_zip: bool,
    selected_tool_ids: List[str],
) -> BuildResult:
    build_root = base_dir / "build_output"
    dist_dir = build_root / "dist"
    work_dir = build_root / "work"
    spec_dir = build_root / "spec"

    build_root.mkdir(exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)

    # persist last selection (handig voor volgende runs)
    try:
        session["exe_builder_selected_tools"] = selected_tool_ids
    except Exception:
        pass

    # entrypoint
    entry = base_dir / "run.py"
    if not entry.exists():
        return BuildResult(False, build_root, None, None, f"[ERROR] run.py niet gevonden in {base_dir}")

    # clean previous onefile name collisions
    exe_name = _safe_name(app_name)
    log: List[str] = []
    log.append(f"Building: {exe_name}")
    log.append(f"Entrypoint: {entry}")
    log.append(f"Output dir: {dist_dir}")
    log.append("")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        exe_name,
        "--onefile",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
    ]

    if icon_ico_path and icon_ico_path.exists():
        cmd += ["--icon", str(icon_ico_path)]

    # include core folders (brand-agnostic)
    for folder_name in ("app", "tools", "config", "assets", "help", "certs"):
        p = base_dir / folder_name
        if p.exists():
            cmd += ["--add-data", _pyinstaller_add_data(p, folder_name)]

    # include selection file for downstream (optioneel)
    sel_file = build_root / "selected_tools.txt"
    try:
        sel_file.write_text("\n".join(selected_tool_ids), encoding="utf-8")
        cmd += ["--add-data", _pyinstaller_add_data(sel_file, "config/selected_tools.txt")]
    except Exception:
        pass

    cmd.append(str(entry))

    rc = _run(cmd, cwd=base_dir, log_lines=log)
    exe_path = dist_dir / f"{exe_name}.exe" if os.name == "nt" else dist_dir / exe_name
    ok = (rc == 0) and exe_path.exists()

    zip_path: Optional[Path] = None
    if ok and include_zip:
        try:
            zip_name = f"{exe_name}_{_now_stamp()}.zip"
            zip_path = build_root / zip_name

            if zip_from_folder is not None:
                zipped = zip_from_folder(dist_dir)
                zip_path.write_bytes(zipped)
            else:
                # fallback zip
                import zipfile
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
                    for p in dist_dir.rglob("*"):
                        if p.is_file():
                            z.write(p, arcname=p.relative_to(dist_dir).as_posix())

            log.append("")
            log.append(f"ZIP created: {zip_path}")
        except Exception as e:
            log.append(f"[WARN] ZIP maken faalde: {e}")

    return BuildResult(ok, build_root, exe_path if ok else None, zip_path, "\n".join(log))


# -----------------------------
# blueprint factory
# -----------------------------
def create_blueprint(get_settings, get_branding, get_tools_cfg) -> Blueprint:
    bp = Blueprint("exe_builder", __name__)

    @bp.route("/exe-builder", methods=["GET", "POST"])
    def index():
        settings = get_settings() or {}
        branding = get_branding() or {}
        tools = _get_tools_list(get_tools_cfg)

        title = _get_title(branding, "EXE Builder")
        base_css = common_css(settings)
        js = common_js()
        header = header_html(settings, title=title, tools=tools, right_html="")
        footer = footer_html(settings)

        # default form values
        app_title = branding.get("app_title") or "Centraal Portaal"
        default_name = _safe_name(app_title, "CentraalPortaal")
        selected_tools = session.get("exe_builder_selected_tools") or [t.get("id") for t in tools if t.get("id")]
        selected_tools = [x for x in selected_tools if isinstance(x, str)]

        result: Optional[BuildResult] = None
        error: Optional[str] = None

        if request.method == "POST":
            app_name = _safe_name(request.form.get("app_name") or default_name, default_name)
            include_zip = (request.form.get("include_zip") == "1")
            selected_tools = request.form.getlist("tools") or []
            selected_tools = [t for t in selected_tools if isinstance(t, str)]

            # icon handling
            icon_ico_path: Optional[Path] = None
            up = request.files.get("logo_png")
            if up and up.filename:
                try:
                    png_bytes = up.read()
                    ico_bytes = _png_to_ico_bytes(png_bytes)
                    build_root = _repo_root() / "build_output"
                    build_root.mkdir(exist_ok=True)
                    icon_ico_path = build_root / f"{app_name}.ico"
                    icon_ico_path.write_bytes(ico_bytes)
                except Exception as e:
                    error = f"Logo verwerken faalde: {e}"

            if not error:
                result = build_exe(
                    base_dir=_repo_root(),
                    app_name=app_name,
                    icon_ico_path=icon_ico_path,
                    include_zip=include_zip,
                    selected_tool_ids=selected_tools,
                )

        tmpl = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>{{ page_title }}</title>
  <style>
    {{ base_css|safe }}
    .card { background:#0a0a0a; border:1px solid #222; border-radius:16px; padding:16px; }
    .grid2 { display:grid; grid-template-columns: 1fr 1fr; gap:16px; }
    input[type="text"], input[type="file"]{
      width:100%; padding:10px; border-radius:12px; border:1px solid #333;
      background:#0b0b0b; color: #ddd;
    }
    .muted{ opacity:.85; }
    .flash-err { background:#221111; border:1px solid #aa3333; padding:10px 12px; border-radius:12px; margin:12px 0; color:#fecaca; }
    .flash-ok { background:#112211; border:1px solid #22aa22; padding:10px 12px; border-radius:12px; margin:12px 0; color:#bbf7d0; }
    .btnrow{ display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; }
    .tool-btn{
      display:inline-block; padding:10px 14px; border-radius:12px;
      border:1px solid #333; background:#111; color:#ddd; text-decoration:none; cursor:pointer;
    }
    .tool-btn:hover{ border-color: rgba(0,247,0,.35); }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
    .logbox{ white-space:pre-wrap; background:#070707; border:1px solid #222; border-radius:12px; padding:12px; margin-top:12px; max-height:420px; overflow:auto; }
    .toolslist{ display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap:8px; }
    .pill{ display:flex; align-items:center; gap:10px; padding:8px 10px; border:1px solid #222; border-radius:12px; background:#0b0b0b; }
    @media (max-width: 980px){ .toolslist{ grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 640px){ .grid2{ grid-template-columns: 1fr; } .toolslist{ grid-template-columns: 1fr; } }
  </style>
  <script>{{ js|safe }}</script>
</head>
<body>
  {{ header|safe }}
  <div class="page">
    <div class="card">
      <h1 style="margin-top:0">{{ page_title }}</h1>
      <p class="muted">Bouw een standalone EXE van deze Tools Hub via PyInstaller. (Windows aanbevolen)</p>

      {% if error %}
        <div class="flash-err">{{ error }}</div>
      {% endif %}

      <form method="post" enctype="multipart/form-data">
        <div class="grid2">
          <div>
            <label><strong>App/EXE naam</strong></label>
            <input type="text" name="app_name" value="{{ default_name }}">
            <div class="muted" style="margin-top:6px;">Dit wordt de bestandsnaam (zonder .exe).</div>

            <div style="margin-top:14px;">
              <label><strong>Logo (PNG) → icon.ico</strong></label>
              <input type="file" name="logo_png" accept="image/png">
              <div class="muted" style="margin-top:6px;">Optioneel. Als je niets uploadt, gebruikt PyInstaller de default icon.</div>
            </div>

            <div style="margin-top:14px; display:flex; align-items:center; gap:10px;">
              <input type="checkbox" id="zip" name="include_zip" value="1">
              <label for="zip"><strong>Maak ook ZIP bundel</strong></label>
            </div>

            <div class="btnrow">
              <button class="tool-btn" type="submit">Build</button>
              <a class="tool-btn" href="{{ url_for('home.index') }}">Home</a>
            </div>
          </div>

          <div>
            <label><strong>Selecteer tools (metadata)</strong></label>
            <div class="muted" style="margin:6px 0 10px;">Deze lijst schrijft naar <span class="mono">build_output/selected_tools.txt</span> en wordt mee opgenomen in de build (optioneel voor toekomstige filtering).</div>
            <div class="toolslist">
              {% for t in tools %}
                <label class="pill">
                  <input type="checkbox" name="tools" value="{{ t.id }}" {{ 'checked' if t.id in selected_tools else '' }}>
                  <span>{{ t.name }}</span>
                </label>
              {% endfor %}
            </div>
          </div>
        </div>
      </form>

      {% if result %}
        {% if result.ok %}
          <div class="flash-ok" style="margin-top:12px;">
            ✅ Build OK
            {% if result.exe_path %}
              · <a href="{{ url_for('exe_builder.download', kind='exe') }}">Download EXE</a>
            {% endif %}
            {% if result.zip_path %}
              · <a href="{{ url_for('exe_builder.download', kind='zip') }}">Download ZIP</a>
            {% endif %}
          </div>
        {% else %}
          <div class="flash-err" style="margin-top:12px;">❌ Build faalde. Check log hieronder.</div>
        {% endif %}

        <div class="logbox mono">{{ result.log_text }}</div>
      {% endif %}
    </div>
  </div>
  {{ footer|safe }}
</body>
</html>
        """

        # stash result paths for download route
        if result is not None:
            session["exe_builder_last_exe"] = str(result.exe_path) if result.exe_path else ""
            session["exe_builder_last_zip"] = str(result.zip_path) if result.zip_path else ""

        return render_template_string(
            tmpl,
            base_css=base_css,
            js=js,
            header=header,
            footer=footer,
            page_title=title,
            tools=tools,
            default_name=default_name,
            selected_tools=selected_tools,
            result=result,
            error=error,
        )

    @bp.route("/exe-builder/download/<kind>", methods=["GET"])
    def download(kind: str):
        kind = (kind or "").lower().strip()
        if kind == "exe":
            p = Path(session.get("exe_builder_last_exe") or "")
        elif kind == "zip":
            p = Path(session.get("exe_builder_last_zip") or "")
        else:
            return make_response("Onbekend download type.", 400)

        if not p.exists() or not p.is_file():
            return make_response("Bestand niet gevonden. Bouw eerst opnieuw.", 404)

        return send_file(p, as_attachment=True, download_name=p.name)

    return bp
