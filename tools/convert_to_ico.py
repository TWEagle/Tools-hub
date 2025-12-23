#!/usr/bin/env python3
"""
tools/convert_to_ico.py  (Tools Hub)

Image → ICO Converter (brand-agnostic).

Route:
- GET/POST  /ico

Features:
- Upload PNG/JPG/GIF/WebP and download a multi-size .ico
- Choose sizes (comma-separated) and a "contain" mode
- Optional transparent padding so non-square images become square nicely
- Uses central layout helpers from app/layout.py if available

Dependencies:
- Pillow
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import List, Tuple

from flask import Blueprint, request, render_template_string, send_file, make_response

try:
    from PIL import Image, ImageOps
except Exception as e:  # pragma: no cover
    Image = None
    ImageOps = None

# ---- optional central layout ----
try:
    from app.layout import common_css, header_html, footer_html, common_js
except Exception:  # pragma: no cover
    def common_css(settings: dict) -> str:
        return "body{font-family:Arial,sans-serif;background:#0b0b0b;color:#ddd;margin:0} .page{padding:20px}"
    def header_html(settings: dict, title: str, tools: list | None = None, right_html: str = "") -> str:
        return f"<div style='padding:12px 16px;border-bottom:1px solid #222;background:#111'><b>{title}</b></div>"
    def footer_html(settings: dict) -> str:
        return "<div style='padding:10px 16px;border-top:1px solid #222;background:#111;text-align:right;font-size:.9em'>© CyNiT 2024 - 2026</div>"
    def common_js() -> str:
        return ""


DEFAULT_SIZES = "16,24,32,48,64,96,128,256"


def _parse_sizes(s: str) -> List[int]:
    out: List[int] = []
    for part in (s or "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            n = int(part)
        except ValueError:
            continue
        if 8 <= n <= 512 and n not in out:
            out.append(n)
    if not out:
        out = [16, 24, 32, 48, 64, 96, 128, 256]
    return out


def _safe_stem(filename: str) -> str:
    stem = Path(filename or "icon").stem or "icon"
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in stem)
    return safe[:80] or "icon"


def _make_square(img: "Image.Image", pad_color=(0, 0, 0, 0)) -> "Image.Image":
    """
    Center-pad to square without distortion.
    """
    w, h = img.size
    if w == h:
        return img
    side = max(w, h)
    out = Image.new("RGBA", (side, side), pad_color)
    out.paste(img, ((side - w) // 2, (side - h) // 2))
    return out


def _contain(img: "Image.Image", size: int) -> "Image.Image":
    """
    Scale to fit within size x size, preserving aspect.
    """
    return ImageOps.contain(img, (size, size), method=Image.LANCZOS)


def _center_on_canvas(img: "Image.Image", size: int, bg=(0, 0, 0, 0)) -> "Image.Image":
    """
    Place img centered on size x size canvas.
    """
    out = Image.new("RGBA", (size, size), bg)
    w, h = img.size
    out.paste(img, ((size - w) // 2, (size - h) // 2), img if img.mode == "RGBA" else None)
    return out


def _build_ico_bytes(img: "Image.Image", sizes: List[int], mode: str, pad: bool) -> bytes:
    """
    mode:
      - "crop"   -> square crop (fills canvas)
      - "contain"-> keep aspect + padding to square
    pad: if True, first make source square by padding (helps before resizing)
    """
    if img.mode not in ("RGBA", "RGB"):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGBA")

    # normalize orientation (EXIF)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    if pad:
        img = _make_square(img)

    ico_imgs: List["Image.Image"] = []
    for s in sizes:
        if mode == "contain":
            scaled = _contain(img, s)
            framed = _center_on_canvas(scaled, s)
            ico_imgs.append(framed)
        else:
            # crop to square and resize
            cropped = ImageOps.fit(img, (s, s), method=Image.LANCZOS, centering=(0.5, 0.5))
            ico_imgs.append(cropped)

    # Pillow can save ICO with multiple sizes using sizes=
    bio = io.BytesIO()
    base = ico_imgs[-1] if ico_imgs else img
    size_tuples: List[Tuple[int, int]] = [(s, s) for s in sizes]
    base.save(bio, format="ICO", sizes=size_tuples)
    return bio.getvalue()


def create_blueprint(get_settings, get_branding, get_tools_cfg) -> Blueprint:
    bp = Blueprint("ico_converter", __name__)

    @bp.route("/ico", methods=["GET", "POST"])
    def index():
        settings = get_settings() or {}
        branding = get_branding() or {}
        tools_cfg = get_tools_cfg() or {"tools": []}
        tools = tools_cfg.get("tools", []) if isinstance(tools_cfg, dict) else []

        title = (branding.get("titles", {}) or {}).get("ico_converter") \
                or branding.get("app_title") \
                or "Image → ICO Converter"

        base_css = common_css(settings)
        js = common_js()
        header = header_html(settings, title=title, tools=tools, right_html="")
        footer = footer_html(settings)

        err = None

        sizes_str = (request.form.get("sizes") or DEFAULT_SIZES).strip()
        mode = (request.form.get("mode") or "contain").strip().lower()
        pad = (request.form.get("pad") == "1")

        if request.method == "POST":
            if Image is None:
                return make_response("Pillow ontbreekt. Installeer 'pillow' in je venv.", 500)

            up = request.files.get("file")
            if not up or not up.filename:
                err = "Geen afbeelding gekozen."
            else:
                try:
                    sizes = _parse_sizes(sizes_str)
                    if mode not in ("contain", "crop"):
                        mode = "contain"

                    raw = up.read()
                    img = Image.open(io.BytesIO(raw))
                    out = _build_ico_bytes(img, sizes=sizes, mode=mode, pad=pad)

                    safe = _safe_stem(up.filename)
                    dl = f"{safe}.ico"
                    bio = io.BytesIO(out)
                    bio.seek(0)
                    return send_file(
                        bio,
                        as_attachment=True,
                        download_name=dl,
                        mimetype="image/x-icon",
                    )
                except Exception as e:
                    err = f"Conversie faalde: {e}"

        tmpl = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>{{ page_title }}</title>
  <style>
    {{ base_css|safe }}
    .card { background:#0a0a0a; border:1px solid #222; border-radius:16px; padding:16px; }
    input[type="file"], input[type="text"], select {
      width:100%; padding:10px; border-radius:12px; border:1px solid #333;
      background:#0b0b0b; color:#ddd;
    }
    .grid { display:grid; grid-template-columns: 1.2fr 1fr; gap:14px; }
    .row { display:grid; grid-template-columns: 1fr 1fr 1fr; gap:12px; align-items:end; }
    .muted{ opacity:.85; }
    .flash-err { background:#221111; border:1px solid #aa3333; padding:10px 12px; border-radius:12px; margin:12px 0; color:#fecaca; }
    .tool-btn{
      display:inline-block; padding:10px 14px; border-radius:12px;
      border:1px solid #333; background:#111; color:#ddd; text-decoration:none; cursor:pointer;
    }
    .tool-btn:hover{ border-color: rgba(0,247,0,.35); }
    .btnrow{ display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; }
    .help { font-size:.92rem; color:#aab; }
    code { background:#111; border:1px solid #222; padding:2px 6px; border-radius:8px; }
  </style>
  <script>{{ js|safe }}</script>
</head>
<body>
  {{ header|safe }}
  <div class="page">
    <div class="card">
      <h1 style="margin-top:0">{{ page_title }}</h1>
      <p class="muted">Upload een afbeelding en download een multi-size <code>.ico</code> bestand.</p>

      {% if err %}
        <div class="flash-err">{{ err }}</div>
      {% endif %}

      <form method="post" enctype="multipart/form-data">
        <div class="grid">
          <div>
            <label><strong>Afbeelding</strong></label>
            <input type="file" name="file" accept="image/*">
            <div class="help" style="margin-top:8px;">PNG/JPG/GIF/WebP. Transparantie blijft behouden (waar mogelijk).</div>
          </div>
          <div>
            <label><strong>Sizes</strong></label>
            <input type="text" name="sizes" value="{{ sizes_str }}" placeholder="16,24,32,48,64,128,256">
            <div class="help" style="margin-top:8px;">
              Komma-separated. Typical: <code>{{ default_sizes }}</code>
            </div>
          </div>
        </div>

        <div class="row" style="margin-top:14px;">
          <div>
            <label><strong>Mode</strong></label>
            <select name="mode">
              <option value="contain" {{ 'selected' if mode=='contain' else '' }}>Contain (geen vervorming, padding)</option>
              <option value="crop" {{ 'selected' if mode=='crop' else '' }}>Crop (vult volledig, kan afsnijden)</option>
            </select>
          </div>
          <div>
            <label><strong>Pad to square</strong></label>
            <label class="help" style="display:flex;gap:10px;align-items:center;">
              <input type="checkbox" name="pad" value="1" {{ 'checked' if pad else '' }}>
              Eerst padding naar vierkant (handig bij heel brede/hoge images)
            </label>
          </div>
          <div class="btnrow" style="justify-content:flex-end;">
            <button class="tool-btn" type="submit">Convert → ICO</button>
          </div>
        </div>
      </form>
    </div>

    <div class="card" style="margin-top:16px;">
      <h2 style="margin-top:0">Tips</h2>
      <ul class="help">
        <li>Voor Windows app icons: gebruik zeker <code>16,24,32,48,64,128,256</code>.</li>
        <li>Als je logo niet vierkant is: kies <b>Contain</b> en zet <b>Pad to square</b> aan.</li>
      </ul>
    </div>
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
            page_title=title,
            err=err,
            sizes_str=sizes_str,
            default_sizes=DEFAULT_SIZES,
            mode=mode,
            pad=pad,
        )

    return bp
