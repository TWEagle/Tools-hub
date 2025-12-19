#!/usr/bin/env python3
"""
tools/cert_viewer.py

Certificate / CSR Viewer (brand-agnostic) voor Tools Hub.

Routes:
- GET/POST  /cert
- GET       /cert/download/<fmt>      (json|csv|html|md|xlsx)
- GET       /cert/download/zip_all
- GET       /cert/save_md
"""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

from flask import Blueprint, request, render_template_string, make_response, send_file, session

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa, dsa, ec

# --- Central layout (preferred) ---
try:
    from app.layout import common_css, header_html, footer_html, common_js
except Exception:  # fallback minimal
    def common_css(settings: dict) -> str:
        return "body{font-family:Arial,sans-serif;background:#0b0b0b;color:#ddd;margin:0} .page{padding:20px}"
    def header_html(settings: dict, title: str, tools: list | None = None, right_html: str = "") -> str:
        return f"<div style='padding:12px 16px;border-bottom:1px solid #222;background:#111'><b>{title}</b></div>"
    def footer_html(settings: dict) -> str:
        return "<div style='padding:10px 16px;border-top:1px solid #222;background:#111;text-align:right;font-size:.9em'>© CyNiT 2024 - 2026</div>"
    def common_js() -> str:
        return ""

# --- Central exports (preferred) ---
try:
    from app import exports as hub_exports
except Exception:
    hub_exports = None

_B64_RE = re.compile(r"^[A-Za-z0-9+/=\s]+$")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _strip_xml_wrapper(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _try_base64_to_der_bytes(text: str) -> Optional[bytes]:
    if not text:
        return None
    t = _strip_xml_wrapper(text.strip()).strip()
    if "BEGIN " in t or "END " in t:
        return None
    if not _B64_RE.match(t):
        return None
    b64 = "".join(t.split())
    try:
        return base64.b64decode(b64, validate=False)
    except Exception:
        return None


def _normalize_pem(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").replace("\r\n", "\n").split("\n") if ln.strip()]
    return "\n".join(lines) + "\n" if lines else ""


def load_cert_or_csr(data: bytes) -> Tuple[str, Any]:
    text: Optional[str] = None
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        text = None

    if text:
        stripped = text.strip()

        # PEM CSR
        if "BEGIN CERTIFICATE REQUEST" in stripped or "BEGIN NEW CERTIFICATE REQUEST" in stripped:
            norm = _normalize_pem(stripped)
            try:
                csr = x509.load_pem_x509_csr(norm.encode("ascii", errors="ignore"))
                return "csr", csr
            except Exception:
                csr = x509.load_pem_x509_csr(data)
                return "csr", csr

        # PEM CERT
        if "BEGIN CERTIFICATE" in stripped and "REQUEST" not in stripped:
            cert = x509.load_pem_x509_certificate(data)
            return "cert", cert

        # plain base64 -> DER
        der = _try_base64_to_der_bytes(stripped)
        if der:
            try:
                cert = x509.load_der_x509_certificate(der)
                return "cert", cert
            except Exception:
                csr = x509.load_der_x509_csr(der)
                return "csr", csr

    # DER CERT
    try:
        cert = x509.load_der_x509_certificate(data)
        return "cert", cert
    except Exception:
        pass

    # DER CSR
    csr = x509.load_der_x509_csr(data)
    return "csr", csr


def _name_to_dict(name: x509.Name) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for attr in name:
        key = attr.oid._name or attr.oid.dotted_string
        out[key] = attr.value
    return out


def _pubkey_summary(pub) -> str:
    try:
        if isinstance(pub, rsa.RSAPublicKey):
            return f"RSA {pub.key_size} bits"
        if isinstance(pub, dsa.DSAPublicKey):
            return f"DSA {pub.key_size} bits"
        if isinstance(pub, ec.EllipticCurvePublicKey):
            return f"EC {pub.curve.name}"
        return pub.__class__.__name__
    except Exception:
        return "unknown"


def _hash_name(sig_hash) -> str:
    try:
        return sig_hash.name
    except Exception:
        return "unknown"


def decode_cert_from_bytes(data: bytes, filename: str = "input") -> Dict[str, Any]:
    kind, obj = load_cert_or_csr(data)

    info: Dict[str, Any] = {
        # compat: jouw exports gebruikte "type"
        "type": kind,
        "kind": kind,

        "filename": filename,
        "decoded_at_utc": _now_utc().isoformat(),
        "subject": {},
        "issuer": None,   # CSR: None zodat "CSR heeft geen issuer" logic klopt
        "properties": {},
        "extensions": [],
        "checks": [],
    }

    if kind == "cert":
        cert: x509.Certificate = obj
        info["subject"] = _name_to_dict(cert.subject)
        info["issuer"] = _name_to_dict(cert.issuer)

        props = info["properties"]
        props["serial_number"] = str(cert.serial_number)
        props["not_valid_before_utc"] = cert.not_valid_before.replace(tzinfo=timezone.utc).isoformat()
        props["not_valid_after_utc"] = cert.not_valid_after.replace(tzinfo=timezone.utc).isoformat()
        props["signature_hash"] = _hash_name(cert.signature_hash_algorithm)
        props["public_key"] = _pubkey_summary(cert.public_key())

        now = _now_utc()
        if cert.not_valid_before.replace(tzinfo=timezone.utc) > now:
            info["checks"].append({"name": "validity", "status": "WARN", "message": "Certificate is nog niet geldig (not_before ligt in de toekomst)."})
        if cert.not_valid_after.replace(tzinfo=timezone.utc) < now:
            info["checks"].append({"name": "validity", "status": "FAIL", "message": "Certificate is verlopen (not_after ligt in het verleden)."})
        if not info["checks"]:
            info["checks"].append({"name": "validity", "status": "OK", "message": "Validity window OK t.o.v. huidige UTC tijd."})

        for ext in cert.extensions:
            info["extensions"].append({
                "oid": ext.oid.dotted_string,
                "name": getattr(ext.oid, "_name", None) or "extension",
                "critical": bool(ext.critical),
                "value": str(ext.value)[:8000],
            })

    else:
        csr: x509.CertificateSigningRequest = obj
        info["subject"] = _name_to_dict(csr.subject)
        info["issuer"] = None

        props = info["properties"]
        props["signature_hash"] = _hash_name(csr.signature_hash_algorithm)
        props["public_key"] = _pubkey_summary(csr.public_key())

        for ext in csr.extensions:
            info["extensions"].append({
                "oid": ext.oid.dotted_string,
                "name": getattr(ext.oid, "_name", None) or "extension",
                "critical": bool(ext.critical),
                "value": str(ext.value)[:8000],
            })

        info["checks"].append({"name": "issuer", "status": "INFO", "message": "CSR heeft geen issuer (wordt pas ingevuld bij certificate issuance)."})

    return info


def create_blueprint(get_settings, get_branding, get_tools_cfg) -> Blueprint:
    bp = Blueprint("cert_viewer", __name__)

    def _get_last_info() -> Optional[Dict[str, Any]]:
        return session.get("cert_last_info")

    def _set_last_info(info: Dict[str, Any]) -> None:
        session["cert_last_info"] = info

    @bp.route("/cert", methods=["GET", "POST"])
    def index():
        settings = get_settings() or {}
        branding = get_branding() or {}
        tools_cfg = get_tools_cfg() or {"tools": []}
        tools = tools_cfg.get("tools", []) if isinstance(tools_cfg, dict) else []

        title = (branding.get("titles", {}) or {}).get("cert_viewer") \
            or branding.get("app_title") \
            or "Certificate / CSR Viewer"

        base_css = common_css(settings)
        js = common_js()
        header = header_html(settings, title=title, tools=tools, right_html="")
        footer = footer_html(settings)

        error = None
        info_obj = None

        if request.method == "POST":
            pasted = (request.form.get("pasted") or "").strip()
            up = request.files.get("file")

            try:
                if up and up.filename:
                    data = up.read()
                    info_obj = decode_cert_from_bytes(data, filename=up.filename)
                    _set_last_info(info_obj)
                elif pasted:
                    if "BEGIN " in pasted:
                        data = _normalize_pem(pasted).encode("utf-8", errors="ignore")
                    else:
                        der = _try_base64_to_der_bytes(pasted)
                        if not der:
                            raise ValueError("Kon pasted input niet herkennen als PEM of Base64 DER.")
                        data = der
                    info_obj = decode_cert_from_bytes(data, filename="pasted.txt")
                    _set_last_info(info_obj)
                else:
                    raise ValueError("Geen bestand gekozen en niets geplakt.")
            except Exception as e:
                error = f"Fout bij decoderen: {e}"

        if info_obj is None:
            info_obj = _get_last_info()

        tmpl = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>{{ page_title }}</title>
  <style>
    {{ base_css|safe }}
    .card { background:#0a0a0a; border:1px solid #222; border-radius:16px; padding:16px; }
    .grid { display:grid; grid-template-columns: 1fr 1fr; gap:16px; }
    textarea, input[type="file"]{
      width:100%; padding:10px; border-radius:12px; border:1px solid #333;
      background:#0b0b0b; color: #ddd;
    }
    table { width:100%; border-collapse: collapse; margin-top:10px; }
    th, td { border:1px solid #222; padding:8px 10px; vertical-align: top; }
    th { width: 34%; background:#101010; text-align:left; }
    .muted{ opacity:.85; }
    .flash-err { background:#221111; border:1px solid #aa3333; padding:10px 12px; border-radius:12px; margin:12px 0; color:#fecaca; }
    .btnrow{ display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; }
    .tool-btn{
      display:inline-block; padding:10px 14px; border-radius:12px;
      border:1px solid #333; background:#111; color:#ddd; text-decoration:none; cursor:pointer;
    }
    .tool-btn:hover{ border-color: rgba(0,247,0,.35); }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
    .badge{ display:inline-block; padding:4px 10px; border-radius:999px; border:1px solid #333; background:#111; font-size:.85rem; }
  </style>
  <script>{{ js|safe }}</script>
</head>
<body>
  {{ header|safe }}
  <div class="page">
    <div class="card">
      <h1 style="margin-top:0">{{ page_title }}</h1>
      <p class="muted">Upload een certificate/CSR (PEM/DER) of plak PEM/Base64.</p>

      {% if error %}
        <div class="flash-err">{{ error }}</div>
      {% endif %}

      <form method="post" enctype="multipart/form-data">
        <div class="grid">
          <div>
            <label><strong>Bestand upload</strong></label>
            <input type="file" name="file">
          </div>
          <div>
            <label><strong>Of plak PEM / Base64</strong></label>
            <textarea name="pasted" rows="6" placeholder="-----BEGIN CERTIFICATE----- ... of Base64 DER ..."></textarea>
          </div>
        </div>

        <div class="btnrow">
          <button class="tool-btn" type="submit">Decode</button>

          {% if info %}
            <a class="tool-btn" href="/cert/download/json">JSON</a>
            <a class="tool-btn" href="/cert/download/csv">CSV</a>
            <a class="tool-btn" href="/cert/download/xlsx">XLSX</a>
            <a class="tool-btn" href="/cert/download/html">HTML</a>
            <a class="tool-btn" href="/cert/download/md">MD</a>
            <a class="tool-btn" href="/cert/download/zip_all">ZIP (all)</a>
            <a class="tool-btn" href="/cert/save_md">Save MD → exports/</a>
          {% endif %}
        </div>
      </form>
    </div>

    {% if info %}
      <div class="card" style="margin-top:16px;">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;">
          <h2 style="margin:0">Decoded</h2>
          <div class="badge mono">{{ info.kind }} · {{ info.filename }}</div>
        </div>

        {% if info.checks %}
          <h3>Checks</h3>
          <table>
            <tbody>
              {% for c in info.checks %}
                <tr><th class="mono">{{ c.name }}</th><td><span class="badge mono">{{ c.status }}</span> {{ c.message }}</td></tr>
              {% endfor %}
            </tbody>
          </table>
        {% endif %}

        <h3>Subject</h3>
        <table>
          <tbody>
            {% for k, v in (info.subject or {}).items() %}
              <tr><th class="mono">{{ k }}</th><td class="mono">{{ v }}</td></tr>
            {% endfor %}
          </tbody>
        </table>

        <h3>Issuer</h3>
        {% if info.issuer %}
          <table>
            <tbody>
              {% for k, v in (info.issuer or {}).items() %}
                <tr><th class="mono">{{ k }}</th><td class="mono">{{ v }}</td></tr>
              {% endfor %}
            </tbody>
          </table>
        {% else %}
          <p class="muted">CSR heeft geen issuer; dit wordt pas ingevuld na uitgifte van het certificaat.</p>
        {% endif %}

        <h3>Properties</h3>
        <table>
          <tbody>
            {% for k, v in (info.properties or {}).items() %}
              <tr><th class="mono">{{ k }}</th><td class="mono">{{ v }}</td></tr>
            {% endfor %}
          </tbody>
        </table>

        {% if info.extensions %}
          <h3>Extensions</h3>
          <table>
            <tbody>
              {% for e in info.extensions %}
                <tr>
                  <th class="mono">{{ e.name }}</th>
                  <td class="mono">
                    <div>OID: {{ e.oid }}{% if e.critical %} · <b>critical</b>{% endif %}</div>
                    <div style="margin-top:6px; white-space:pre-wrap;">{{ e.value }}</div>
                  </td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
        {% endif %}
      </div>
    {% endif %}

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
            error=error,
            info=info_obj,
        )

    @bp.route("/cert/download/<fmt>", methods=["GET"])
    def download(fmt: str):
        settings = get_settings() or {}
        branding = get_branding() or {}
        info = session.get("cert_last_info")
        if not info:
            return make_response("Nog geen certificaat/CSR gedecodeerd in deze sessie.", 400)

        base_name = Path(info.get("filename", "certificate")).stem or "certificate"
        fmt = (fmt or "").lower().strip()

        # JSON direct
        if fmt == "json":
            content = json.dumps(info, indent=2, ensure_ascii=False)
            resp = make_response(content)
            resp.headers["Content-Type"] = "application/json; charset=utf-8"
            resp.headers["Content-Disposition"] = f'attachment; filename="{base_name}.json"'
            return resp

        # CSV (via hub_exports als die build heeft, anders simpele fallback)
        if fmt == "csv":
            if hub_exports and hasattr(hub_exports, "build_csv_text"):
                content = hub_exports.build_csv_text(info)
            else:
                lines = ["Section;Field;Value"]
                for sec_key, sec_name in [("subject", "Subject"), ("issuer", "Issuer"), ("properties", "Properties")]:
                    section = info.get(sec_key)
                    if not isinstance(section, dict):
                        continue
                    for k, v in section.items():
                        lines.append(f"{sec_name};{k};{str(v).replace(';', ',')}")
                content = "\n".join(lines)

            resp = make_response(content)
            resp.headers["Content-Type"] = "text/csv; charset=utf-8"
            resp.headers["Content-Disposition"] = f'attachment; filename="{base_name}.csv"'
            return resp

        # HTML / MD / XLSX / ZIP via centrale exports (asap)
        if hub_exports and hasattr(hub_exports, "build_html_export") and fmt == "html":
            html_out = hub_exports.build_html_export(info, settings, branding)
            return make_response(html_out, 200, {
                "Content-Type": "text/html; charset=utf-8",
                "Content-Disposition": f'attachment; filename="{base_name}.html"',
            })

        if hub_exports and hasattr(hub_exports, "build_markdown_export") and fmt == "md":
            md = hub_exports.build_markdown_export(info, settings, branding)
            return make_response(md, 200, {
                "Content-Type": "text/markdown; charset=utf-8",
                "Content-Disposition": f'attachment; filename="{base_name}.md"',
            })

        if hub_exports and hasattr(hub_exports, "build_xlsx_export") and fmt == "xlsx":
            data = hub_exports.build_xlsx_export(info, settings, branding)
            buf = BytesIO(data)
            buf.seek(0)
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{base_name}.xlsx",
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        return make_response("Exporttype nog niet beschikbaar (exports module nog niet uitgebreid).", 400)

    @bp.route("/cert/download/zip_all", methods=["GET"])
    def zip_all():
        settings = get_settings() or {}
        branding = get_branding() or {}
        info = session.get("cert_last_info")
        if not info:
            return make_response("Nog geen certificaat/CSR gedecodeerd in deze sessie.", 400)

        if not (hub_exports and hasattr(hub_exports, "build_zip_bytes")):
            return make_response("ZIP export nog niet beschikbaar (exports module nog niet uitgebreid).", 400)

        formats = ["json", "csv", "xlsx", "html", "md"]
        zip_bytes = hub_exports.build_zip_bytes(info, settings, branding, formats)
        base_name = Path(info.get("filename", "certificate")).stem or "certificate"

        buf = BytesIO(zip_bytes)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name=f"{base_name}_all.zip", mimetype="application/zip")

    @bp.route("/cert/save_md", methods=["GET"])
    def save_md():
        settings = get_settings() or {}
        branding = get_branding() or {}
        info = session.get("cert_last_info")
        if not info:
            return make_response("Nog geen certificaat/CSR gedecodeerd in deze sessie.", 400)

        if not (hub_exports and hasattr(hub_exports, "ensure_exports_dir") and hasattr(hub_exports, "build_markdown_export")):
            return make_response("Save MD nog niet beschikbaar (exports module nog niet uitgebreid).", 400)

        hub_exports.ensure_exports_dir()

        orig_name = info.get("filename", "certificate")
        slug = hub_exports.slugify_filename(orig_name) if hasattr(hub_exports, "slugify_filename") else (Path(orig_name).stem or "certificate")
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{slug}_{ts}.md"
        dest = hub_exports.EXPORTS_DIR / filename

        md = hub_exports.build_markdown_export(info, settings, branding)
        dest.write_text(md, encoding="utf-8")

        return make_response(
            f"<html><body style='font-family:Arial;padding:20px'>"
            f"<h2>Markdown opgeslagen</h2>"
            f"<p><b>{filename}</b> opgeslagen in exports/.</p>"
            f"<p><a href='/cert'>Terug</a></p>"
            f"</body></html>",
            200,
        )

    return bp
