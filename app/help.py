# app/help.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Blueprint, abort, render_template_string, request, send_file

from .layout import common_css, common_js, header_html, footer_html


def _safe_int(v: Any, default: int, lo: int = 1, hi: int = 6) -> int:
    try:
        x = int(v)
        if x < lo:
            return lo
        if x > hi:
            return hi
        return x
    except Exception:
        return default


def _is_admin() -> bool:
    # Admin cookie (expliciet) of Flask session cookie (signed)
    from flask import session, request
    if session.get("admin_ok") is True:
        return True
    if (request.cookies.get("admin_ok") or "").strip() == "1":
        return True
    return False


def _md_to_html(md_text: str) -> str:
    """
    Markdown -> HTML.
    - Probeert 'markdown' (python-markdown).
    - Fallback: minimal.
    """
    try:
        import markdown  # type: ignore

        return markdown.markdown(
            md_text,
            extensions=[
                "fenced_code",
                "tables",
                "toc",
                "codehilite",
            ],
            output_format="html5",
        )
    except Exception:
        # super simpele fallback
        esc = (
            md_text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return "<pre style='white-space:pre-wrap'>" + esc + "</pre>"


def _normalize_categories(cfg: Dict[str, Any], items_key: str) -> List[Dict[str, Any]]:
    """
    Verwacht:
      cfg["categories"] = [{id,label,color,enabled,columns}, ...]
    Items hebben "category".
    We zorgen dat elke gebruikte category bestaat.
    """
    items = cfg.get(items_key) or []
    cats = cfg.get("categories")
    out: List[Dict[str, Any]] = []
    seen = set()

    if isinstance(cats, list):
        for c in cats:
            if not isinstance(c, dict):
                continue
            cid = (c.get("id") or "").strip() or "misc"
            if cid in seen:
                continue
            seen.add(cid)
            out.append(
                {
                    "id": cid,
                    "label": (c.get("label") or cid.title()).strip(),
                    "color": (c.get("color") or "#00f700").strip(),
                    "enabled": bool(c.get("enabled", True)),
                    "columns": _safe_int(c.get("columns", 3), 3, 1, 6),
                }
            )

    # add missing categories from items
    for it in items:
        if not isinstance(it, dict):
            continue
        cid = (it.get("category") or "misc").strip() or "misc"
        if cid in seen:
            continue
        seen.add(cid)
        out.append(
            {
                "id": cid,
                "label": cid.title(),
                "color": "#00f700",
                "enabled": True,
                "columns": 3,
            }
        )

    if "misc" not in seen:
        out.append({"id": "misc", "label": "Misc", "color": "#00f700", "enabled": True, "columns": 3})

    return out


def create_help_blueprint(
    base_dir: Path,
    get_settings,
    get_branding,
    get_help_cfg,
) -> Blueprint:
    bp = Blueprint("help", __name__)

    HELP_ROOT_DEFAULT = base_dir / "help"

    @bp.route("/help", methods=["GET"])
    def help_index():
        settings = get_settings() or {}
        branding = get_branding() or {}
        cfg = get_help_cfg() or {"docs": []}

        docs = cfg.get("docs") or []
        if not isinstance(docs, list):
            docs = []

        cats = _normalize_categories(cfg, "docs")

        admin = _is_admin()

        # filter: normale users zien enkel enabled cats+docs
        def cat_enabled(cid: str) -> bool:
            for c in cats:
                if c["id"] == cid:
                    return bool(c.get("enabled", True))
            return True

        visible_docs: List[Dict[str, Any]] = []
        for d in docs:
            if not isinstance(d, dict):
                continue
            did = (d.get("id") or "").strip()
            if not did:
                continue
            d.setdefault("title", d.get("name") or did)
            d.setdefault("enabled", True)
            d.setdefault("category", "misc")
            d["category"] = (d.get("category") or "misc").strip() or "misc"
            if (not admin) and (not bool(d.get("enabled", True))):
                continue
            if (not admin) and (not cat_enabled(d["category"])):
                continue
            visible_docs.append(d)

        # group by category
        by_cat: Dict[str, List[Dict[str, Any]]] = {}
        for d in visible_docs:
            by_cat.setdefault(d["category"], []).append(d)

        # ordering categories as defined
        ordered_cats = [c for c in cats if c["id"] in by_cat]

        base_css = common_css(settings)
        js = common_js()

        header = header_html(settings, branding, title="Help", right_html="")
        footer = footer_html(branding)

        tmpl = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>{{ branding.get('app_title','Centraal Portaal') }} - Help</title>
  <style>
    {{ base_css|safe }}

    .section { margin-top: 18px; }
    .cat-head { display:flex; align-items:center; gap:10px; margin: 16px 0 10px; }
    .cat-dot { width:10px; height:10px; border-radius:999px; background: var(--cat-color); box-shadow: 0 0 18px rgba(0,0,0,0.6); }
    .cat-title { font-size: 1.1rem; font-weight: 800; }
    .cat-sub { opacity:0.75; font-size:0.9rem; }

    .grid {
      display:grid;
      grid-template-columns: repeat(var(--cols), minmax(260px, 1fr));
      gap: 16px;
    }

    .card {
      position: relative;
      background: #0b0b0b;
      border: 1px solid #202020;
      border-radius: 16px;
      padding: 14px 14px 12px 14px;
      box-shadow: 0 16px 30px rgba(0,0,0,0.85);
      transition: transform .15s ease, border-color .15s ease;
      overflow:hidden;
    }
    .card:hover { transform: translateY(-4px); border-color: rgba(0,247,0,0.25); }

    .accent {
      position:absolute; left:0; top:0; bottom:0;
      width: 6px;
      background: var(--cat-color);
      opacity: 0.95;
    }

    .card h3 { margin:0 0 6px 0; font-size:1.0rem; }
    .meta { opacity:0.75; font-size:0.9rem; }
    .actions { margin-top: 10px; display:flex; gap:10px; flex-wrap:wrap; }

    .btn {
      display:inline-block;
      padding: 8px 12px;
      border-radius: 12px;
      border: 1px solid #2a2a2a;
      background: #101010;
      text-decoration:none;
      color: inherit;
      font-weight: 700;
    }
    .btn:hover { border-color: rgba(0,247,0,0.25); }
  </style>
  <script>{{ js|safe }}</script>
</head>
<body>
  {{ header|safe }}
  <div class="page">
    <h1>Help</h1>
    <p class="muted">Alle helpfiles zijn Markdown en worden centraal gerenderd.</p>

    {% if ordered_cats|length == 0 %}
      <div class="card"><div class="accent" style="--cat-color:#00f700"></div>
        <h3>Geen helpfiles</h3>
        <div class="meta">Voeg entries toe in <code>config/help.json</code>.</div>
      </div>
    {% endif %}

    {% for cat in ordered_cats %}
      <div class="section" style="--cat-color: {{ cat.color }}; --cols: {{ cat.columns }};">
        <div class="cat-head">
          <div class="cat-dot"></div>
          <div>
            <div class="cat-title">{{ cat.label }}</div>
            <div class="cat-sub">{{ by_cat[cat.id]|length }} pagina(s)</div>
          </div>
        </div>

        <div class="grid">
          {% for d in by_cat[cat.id] %}
            <div class="card">
              <div class="accent"></div>
              <h3>{{ d.title }}</h3>
              <div class="meta">
                id: {{ d.id }}<br>
                pad: <code>{{ d.path }}</code>
                {% if admin %}
                  <br>enabled: <code>{{ 'true' if d.enabled else 'false' }}</code>
                {% endif %}
              </div>
              <div class="actions">
                <a class="btn" href="{{ url_for('help.view_doc', doc_id=d.id) }}">Open</a>
                <a class="btn" href="{{ url_for('help.download_doc', doc_id=d.id) }}">Download .md</a>
              </div>
            </div>
          {% endfor %}
        </div>
      </div>
    {% endfor %}

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
            branding=branding,
            ordered_cats=ordered_cats,
            by_cat=by_cat,
            admin=admin,
        )

    def _find_doc(doc_id: str) -> Optional[Dict[str, Any]]:
        cfg = get_help_cfg() or {"docs": []}
        docs = cfg.get("docs") or []
        for d in docs:
            if not isinstance(d, dict):
                continue
            if (d.get("id") or "").strip() == doc_id:
                return d
        return None

    def _resolve_path(doc: Dict[str, Any]) -> Path:
        # absolute ok, else relative to base_dir
        p = (doc.get("path") or "").strip()
        if not p:
            return HELP_ROOT_DEFAULT / "missing.md"
        pp = Path(p)
        if pp.is_absolute():
            return pp
        return (base_dir / pp).resolve()

    @bp.route("/help/<doc_id>", methods=["GET"])
    def view_doc(doc_id: str):
        settings = get_settings() or {}
        branding = get_branding() or {}

        doc = _find_doc(doc_id)
        if not doc:
            abort(404)

        p = _resolve_path(doc)
        if not p.exists():
            abort(404)

        md = p.read_text(encoding="utf-8", errors="replace")
        html = _md_to_html(md)

        base_css = common_css(settings)
        js = common_js()
        header = header_html(settings, branding, title=str(doc.get("title") or doc_id), right_html="")
        footer = footer_html(branding)

        tmpl = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>{{ branding.get('app_title','Centraal Portaal') }} - {{ title }}</title>
  <style>
    {{ base_css|safe }}
    .doc { background:#0b0b0b;border:1px solid #222;border-radius:16px;padding:16px; }
    .doc h1:first-child { margin-top:0; }
    pre, code { background:#0f0f0f; border:1px solid #222; border-radius:10px; }
    pre { padding:12px; overflow:auto; }
    code { padding:2px 6px; }
    table { width:100%; border-collapse: collapse; }
    th, td { border:1px solid #222; padding:8px; }
  </style>
  <script>{{ js|safe }}</script>
</head>
<body>
  {{ header|safe }}
  <div class="page">
    <div style="display:flex; gap:10px; flex-wrap:wrap; margin: 8px 0 14px;">
      <a class="tool-btn" href="{{ url_for('help.help_index') }}">← Terug naar Help</a>
      <a class="tool-btn" href="{{ url_for('help.download_doc', doc_id=doc_id) }}">Download .md</a>
    </div>
    <div class="doc">{{ html|safe }}</div>
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
            branding=branding,
            title=str(doc.get("title") or doc_id),
            html=html,
            doc_id=doc_id,
        )

    @bp.route("/help/<doc_id>/download", methods=["GET"])
    def download_doc(doc_id: str):
        doc = _find_doc(doc_id)
        if not doc:
            abort(404)
        p = _resolve_path(doc)
        if not p.exists():
            abort(404)
        return send_file(str(p), as_attachment=True, download_name=p.name)

    return bp
