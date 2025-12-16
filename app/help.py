# app/help.py
from __future__ import annotations

from pathlib import Path
from collections import defaultdict

from flask import Blueprint, abort, render_template_string, session

import markdown as md

from .layout import common_css, common_js, header_html, footer_html


def _enabled_default(it: dict) -> bool:
    return bool(it.get("enabled", True))


def _is_admin() -> bool:
    # compatible met admin.py (session key)
    return session.get("admin_ok") is True


def _normalize_category(value: str | None) -> str:
    c = (value or "misc").strip()
    return c or "misc"


def _safe_resolve_doc_path(base_dir: Path, help_dir: Path, doc_path: str) -> Path:
    """
    Resolve doc_path safely:
    - First try help_dir/doc_path (most common)
    - If doc_path is absolute, allow it only if it is within base_dir or help_dir
    - Prevent path traversal outside allowed roots
    """
    p = Path(doc_path)

    # Prefer help_dir relative path
    if not p.is_absolute():
        candidate = (help_dir / p).resolve()
        # must stay within help_dir
        if help_dir.resolve() in candidate.parents or candidate == help_dir.resolve():
            return candidate

        # fallback: relative to base_dir, but still must remain within base_dir
        candidate2 = (base_dir / p).resolve()
        if base_dir.resolve() in candidate2.parents or candidate2 == base_dir.resolve():
            return candidate2

        return candidate  # will likely 404 later

    # absolute path: allow only if inside base_dir or help_dir
    resolved = p.resolve()
    if help_dir.resolve() in resolved.parents or resolved == help_dir.resolve():
        return resolved
    if base_dir.resolve() in resolved.parents or resolved == base_dir.resolve():
        return resolved

    # deny weird absolute paths
    raise PermissionError("Doc path outside allowed roots")


def _render_markdown(markdown_text: str) -> str:
    # Markdown -> HTML (nice defaults)
    return md.markdown(
        markdown_text,
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "nl2br",
            "sane_lists",
        ],
        output_format="html5",
    )


def create_help_blueprint(base_dir: Path, get_settings, get_branding, get_help_cfg) -> Blueprint:
    bp = Blueprint("help", __name__)

    HELP_DIR = base_dir / "help"
    HELP_DIR.mkdir(exist_ok=True)

    @bp.route("/help")
    def help_index():
        settings = get_settings()
        branding = get_branding() or {}
        help_cfg = get_help_cfg() or {}

        docs = help_cfg.get("docs", []) if isinstance(help_cfg, dict) else []
        categories = help_cfg.get("categories", []) if isinstance(help_cfg, dict) else []

        cat_label = {}
        if isinstance(categories, list):
            for c in categories:
                if isinstance(c, dict) and c.get("id"):
                    cat_label[str(c["id"])] = str(c.get("label") or c["id"]).strip()

        grouped = defaultdict(list)

        for d in docs:
            if not isinstance(d, dict):
                continue
            if (not _enabled_default(d)) and (not _is_admin()):
                continue

            did = (d.get("id") or "").strip()
            title = (d.get("title") or did or "doc").strip()
            path = (d.get("path") or "").strip()
            cat = _normalize_category(d.get("category"))

            grouped[cat].append(
                {
                    "id": did,
                    "title": title,
                    "path": path,
                    "enabled": _enabled_default(d),
                    "category": cat,
                }
            )

        # order: categories list first, then alphabetical leftovers
        ordered_cats = []
        if isinstance(categories, list) and categories:
            for c in categories:
                cid = (c.get("id") if isinstance(c, dict) else None)
                if cid and cid in grouped:
                    ordered_cats.append(cid)
        for c in sorted(grouped.keys()):
            if c not in ordered_cats:
                ordered_cats.append(c)

        # sort docs by title
        for c in ordered_cats:
            grouped[c].sort(key=lambda x: (x["title"] or "").lower())

        base_css = common_css(settings)
        js = common_js()
        header = header_html(settings, title=branding.get("app_title", "Centraal Portaal"), tools=[])
        footer = footer_html()

        tmpl = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>Help</title>
  <style>
    {{ base_css|safe }}
    .panel { background:#0a0a0a;border:1px solid #222;border-radius:16px;padding:14px; }
    .cat { margin: 18px 0 10px; font-size: 1.15rem; }
    .doclist { display:grid; gap:10px; }
    .doc {
      display:flex; justify-content:space-between; align-items:center; gap:12px;
      background:#111; border:1px solid #1b1b1b; border-radius:14px; padding:12px 14px;
      text-decoration:none;
    }
    .doc:hover { border-color: rgba(0,247,0,0.35); background:#141414; }
    .doc .title { font-weight:700; }
    .doc .meta { color:#888; font-size:0.9rem; }
    .pill { padding:4px 10px; border-radius:999px; border:1px solid #333; background:#0b0b0b; color:#aaa; font-size:0.85rem; }
    .pill.off { border-color:#553333; color:#ffb4b4; }
  </style>
  <script>{{ js|safe }}</script>
</head>
<body>
  {{ header|safe }}
  <div class="page">
    <h1>Help</h1>
    <p class="muted">Markdown docs uit <code>help/</code> (config via <code>config/help.json</code>).</p>

    <div class="panel">
      {% if not ordered_cats %}
        <p class="muted">Geen helpdocs gevonden. Zet docs in <code>help/</code> en registreer ze in <code>config/help.json</code>.</p>
      {% endif %}

      {% for cat in ordered_cats %}
        <div class="cat">{{ cat_label.get(cat, cat.title()) }}</div>
        <div class="doclist">
          {% for d in grouped[cat] %}
            <a class="doc" href="/help/{{ d.id }}">
              <div>
                <div class="title">{{ d.title }}</div>
                <div class="meta">{{ d.path }}</div>
              </div>
              {% if admin and not d.enabled %}
                <span class="pill off">disabled</span>
              {% elif admin %}
                <span class="pill">enabled</span>
              {% endif %}
            </a>
          {% endfor %}
        </div>
      {% endfor %}
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
            grouped=grouped,
            ordered_cats=ordered_cats,
            cat_label=cat_label,
            admin=_is_admin(),
        )

    @bp.route("/help/<doc_id>")
    def help_doc(doc_id: str):
        settings = get_settings()
        branding = get_branding() or {}
        help_cfg = get_help_cfg() or {}

        docs = help_cfg.get("docs", []) if isinstance(help_cfg, dict) else []
        doc = None
        for d in docs:
            if isinstance(d, dict) and (d.get("id") or "").strip() == doc_id:
                doc = d
                break

        if not doc:
            abort(404, "Doc not found")

        if (not _enabled_default(doc)) and (not _is_admin()):
            abort(404, "Doc disabled")

        title = (doc.get("title") or doc_id).strip()
        path = (doc.get("path") or "").strip()
        if not path:
            abort(404, "Doc path missing")

        try:
            doc_path = _safe_resolve_doc_path(base_dir, HELP_DIR, path)
        except PermissionError:
            abort(403, "Invalid doc path")

        if not doc_path.exists():
            abort(404, f"File not found: {doc_path.name}")

        raw = doc_path.read_text(encoding="utf-8", errors="replace")
        html = _render_markdown(raw)

        base_css = common_css(settings)
        js = common_js()
        header = header_html(settings, title=branding.get("app_title", "Centraal Portaal"), tools=[])
        footer = footer_html()

        tmpl = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <style>
    {{ base_css|safe }}
    .panel { background:#0a0a0a;border:1px solid #222;border-radius:16px;padding:16px; }
    .doc-actions { display:flex; gap:10px; flex-wrap:wrap; margin: 10px 0 16px; }
    .md h1, .md h2, .md h3 { color: #00A2FF; }
    .md a { text-decoration: underline; }
    .md pre { background:#060606; border:1px solid #222; padding:12px; border-radius:12px; overflow:auto; }
    .md code { background:#060606; border:1px solid #222; }
    .md table { border-collapse: collapse; width:100%; }
    .md th, .md td { border:1px solid #222; padding:8px; }
    .md blockquote { border-left: 3px solid #333; padding-left: 12px; color:#aaa; }
  </style>
  <script>{{ js|safe }}</script>
</head>
<body>
  {{ header|safe }}
  <div class="page">
    <div class="doc-actions">
      <a class="tool-btn" href="/help">← Help</a>
      <span class="muted">Bron: <code>{{ filename }}</code></span>
      {% if admin and not enabled %}
        <span class="muted">· (disabled voor non-admin)</span>
      {% endif %}
    </div>

    <div class="panel md">
      {{ html|safe }}
    </div>
  </div>
  {{ footer|safe }}
</body>
</html>
        """
        return render_template_string(
            tmpl,
            title=title,
            filename=doc_path.name,
            html=html,
            base_css=base_css,
            js=js,
            header=header,
            footer=footer,
            admin=_is_admin(),
            enabled=_enabled_default(doc),
        )

    return bp
