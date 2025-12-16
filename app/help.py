from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from flask import Blueprint, abort, current_app, render_template_string, send_file, url_for

import markdown


HELP_BP = Blueprint("help", __name__)

_SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _slugify(name: str) -> str:
    name = (name or "").strip()
    name = name.replace(" ", "-")
    name = _SLUG_RE.sub("-", name)
    name = name.strip("-").lower()
    return name


@dataclass
class HelpDoc:
    slug: str
    title: str
    path: Path


def _get_paths():
    # core.py stopt dit in app.config["PATHS"]
    paths = current_app.config.get("PATHS")
    if not paths:
        raise RuntimeError("PATHS ontbreekt in app.config. Zet PATHS in core.py")
    return paths


def _extract_title(md_text: str, fallback: str) -> str:
    # 1) eerste "# Titel"
    for line in md_text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip() or fallback
    return fallback


def list_help_docs() -> List[HelpDoc]:
    paths = _get_paths()
    help_dir: Path = paths.help_dir

    docs: List[HelpDoc] = []
    if help_dir.exists():
        for p in sorted(help_dir.rglob("*.md")):
            rel = p.relative_to(help_dir).as_posix()
            slug = _slugify(rel.replace("/", "__"))
            title = p.stem
            docs.append(HelpDoc(slug=slug, title=title, path=p))

    # optioneel: ABOUT.md als fallback doc
    about: Path = paths.default_about
    if about.exists():
        slug = "about"
        docs = [d for d in docs if d.slug != slug]
        docs.insert(0, HelpDoc(slug=slug, title="About", path=about))

    return docs


def find_doc(slug: str) -> Optional[HelpDoc]:
    slug = (slug or "").strip().lower()
    for d in list_help_docs():
        if d.slug == slug:
            return d
    return None


def render_md_to_html(md_text: str) -> str:
    """
    Markdown -> HTML.
    Extensions: tables, fenced_code, toc (handig), sane_lists.
    """
    return markdown.markdown(
        md_text,
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "sane_lists",
        ],
        output_format="html5",
    )


def _wrap_in_layout(title: str, body_html: str) -> str:
    # We gebruiken je bestaande layout helpers als ze bestaan:
    layout = current_app.config.get("LAYOUT_HELPERS")
    if layout:
        base_css = layout["base_css"]()
        header = layout["header"](title)
        footer = layout["footer"]()
        common_js = layout["common_js"]()
    else:
        base_css = ""
        header = f"<div style='padding:14px 18px; background:#0b0b0b; color:#eee; font-family:system-ui;'><b>{title}</b></div>"
        footer = ""
        common_js = ""

    template = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <style>
    {{ base_css|safe }}

    /* docs styling */
    .doc-wrap { max-width: 1100px; margin: 0 auto; padding: 18px; }
    .doc-card { background:#0c0c0c; border:1px solid #1a1a1a; border-radius: 14px; padding: 16px 18px; }
    .doc-meta { display:flex; gap:10px; flex-wrap:wrap; margin-bottom: 12px; }
    .doc-meta a {
      display:inline-block; padding:6px 10px; border-radius:999px;
      background:#111; border:1px solid #222; color:#9fe; text-decoration:none;
      font-family: system-ui;
      font-size: 0.9rem;
    }
    .doc-meta a:hover { filter: brightness(1.15); }

    .doc-card h1, .doc-card h2, .doc-card h3 { margin-top: 14px; }
    .doc-card code { background:#111; padding:2px 6px; border-radius:6px; }
    .doc-card pre {
      background:#060606; border:1px solid #1a1a1a; padding: 12px; border-radius: 12px;
      overflow:auto;
    }
    .doc-card table { width:100%; border-collapse: collapse; margin: 10px 0; }
    .doc-card th, .doc-card td { border:1px solid #222; padding: 8px; }
  </style>
  <script>{{ common_js|safe }}</script>
</head>
<body>
  {{ header|safe }}

  <div class="doc-wrap">
    <div class="doc-card">
      <div class="doc-meta">
        <a href="{{ url_for('help.index') }}">📚 Help index</a>
        {% if download_url %}
          <a href="{{ download_url }}">⬇ Download .md</a>
        {% endif %}
      </div>
      {{ body_html|safe }}
    </div>
  </div>

  {{ footer|safe }}
</body>
</html>
"""
    return render_template_string(
        template,
        title=title,
        base_css=base_css,
        common_js=common_js,
        header=header,
        footer=footer,
        body_html=body_html,
        download_url=None,
    )


@HELP_BP.get("/help")
def index():
    docs = list_help_docs()

    items = []
    for d in docs:
        items.append((d.title, url_for("help.view_doc", slug=d.slug)))

    # simpele index html
    body = ["<h1>Help</h1>", "<ul>"]
    for title, href in items:
        body.append(f"<li><a href='{href}'>{title}</a></li>")
    body.append("</ul>")
    return _wrap_in_layout("Help", "\n".join(body))


@HELP_BP.get("/help/<slug>")
def view_doc(slug: str):
    d = find_doc(slug)
    if not d:
        abort(404)

    md_text = d.path.read_text(encoding="utf-8", errors="replace")
    title = _extract_title(md_text, d.title)
    html = render_md_to_html(md_text)

    # wrapper met download knop
    layout = current_app.config.get("LAYOUT_HELPERS")
    if layout:
        base_css = layout["base_css"]()
        header = layout["header"](title)
        footer = layout["footer"]()
        common_js = layout["common_js"]()
    else:
        base_css = ""
        header = f"<div style='padding:14px 18px; background:#0b0b0b; color:#eee; font-family:system-ui;'><b>{title}</b></div>"
        footer = ""
        common_js = ""

    template = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <style>
    {{ base_css|safe }}
    .doc-wrap { max-width: 1100px; margin: 0 auto; padding: 18px; }
    .doc-card { background:#0c0c0c; border:1px solid #1a1a1a; border-radius: 14px; padding: 16px 18px; }
    .doc-meta { display:flex; gap:10px; flex-wrap:wrap; margin-bottom: 12px; }
    .doc-meta a {
      display:inline-block; padding:6px 10px; border-radius:999px;
      background:#111; border:1px solid #222; color:#9fe; text-decoration:none;
      font-family: system-ui;
      font-size: 0.9rem;
    }
    .doc-meta a:hover { filter: brightness(1.15); }
    .doc-card h1, .doc-card h2, .doc-card h3 { margin-top: 14px; }
    .doc-card code { background:#111; padding:2px 6px; border-radius:6px; }
    .doc-card pre {
      background:#060606; border:1px solid #1a1a1a; padding: 12px; border-radius: 12px;
      overflow:auto;
    }
    .doc-card table { width:100%; border-collapse: collapse; margin: 10px 0; }
    .doc-card th, .doc-card td { border:1px solid #222; padding: 8px; }
  </style>
  <script>{{ common_js|safe }}</script>
</head>
<body>
  {{ header|safe }}

  <div class="doc-wrap">
    <div class="doc-card">
      <div class="doc-meta">
        <a href="{{ url_for('help.index') }}">📚 Help index</a>
        <a href="{{ url_for('help.download_md', slug=slug) }}">⬇ Download .md</a>
      </div>
      {{ body_html|safe }}
    </div>
  </div>

  {{ footer|safe }}
</body>
</html>
"""
    return render_template_string(
        template,
        title=title,
        base_css=base_css,
        common_js=common_js,
        header=header,
        footer=footer,
        body_html=html,
        slug=d.slug,
    )


@HELP_BP.get("/help/<slug>/download")
def download_md(slug: str):
    d = find_doc(slug)
    if not d:
        abort(404)
    return send_file(
        d.path,
        as_attachment=True,
        download_name=d.path.name,
        mimetype="text/markdown; charset=utf-8",
    )
