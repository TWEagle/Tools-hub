#!/usr/bin/env python3
"""
useful_links.py - CyNiT Tools module

- JSON opslag: config/useful_links.json
- Links klikbaar (nieuwe tab), copy knop
- Categorie-filters als vierkante blokken + kleuraccent
- CRUD links (add/edit/delete) + modals
- Tabs bovenaan (Links/Beheer) + sticky
- Categoriebeheer:
  * inline color picker
  * rename via ✏️ of dubbelklik op naam (met live preview)
  * delete (alleen leeg)
- Default category:
  * dropdown om default te kiezen
  * lege categorie bij add/edit => default_category
  * rename default => default volgt automatisch
- Hide toggle verbergt default category (ook in “Alle”)
- View mode:
  * per-tool instelbaar via settings.json
  * UI toggle (compact / comfortabel)
  * keuze wordt opgeslagen in useful_links.json prefs
- Grid columns:
  * slider in Beheer (max columns per mode)
  * schrijft naar config/settings.json -> useful_links.modes.<mode>.max_columns
  * wordt live toegepast (module leest settings.json per request)
- UX:
  * ESC sluit modals
  * klik op overlay sluit modals
  * focus trap (Tab/Shift+Tab blijft binnen modal)
  * focus op 1e veld bij open
  * Ctrl+Enter = opslaan (modals)
  * Ctrl+S = opslaan (modals)
  * Ctrl+W = sluit modal (als modal open is)
  * Enter submit in modals uitgeschakeld (behalve wanneer focus op button)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from flask import Flask, request, render_template_string, redirect, url_for

import cynit_theme
import cynit_layout


BASE_DIR: Path = cynit_theme.BASE_DIR
CONFIG_DIR: Path = cynit_theme.CONFIG_DIR
DATA_PATH: Path = CONFIG_DIR / "useful_links.json"


FALLBACK_CATEGORY = "General"
DEFAULT_COLOR = "#00f700"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _default_db() -> Dict[str, Any]:
    return {
        "version": 10,
        "prefs": {
            "default_category": FALLBACK_CATEGORY,
            "hide_default_category": False,
            "view_mode": "comfortable",  # 'comfortable' or 'compact'
        },
        "categories": {
            FALLBACK_CATEGORY: {"color": DEFAULT_COLOR},
        },
        "links": [],
    }


def save_db(db: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")


def _normalize_category_name(name: str) -> str:
    return (name or "").strip()


def load_db() -> Dict[str, Any]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not DATA_PATH.exists():
        db = _default_db()
        save_db(db)
        return db

    try:
        db = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        db = _default_db()

    if not isinstance(db, dict):
        db = _default_db()

    changed = False

    if not isinstance(db.get("links"), list):
        db["links"] = []
        changed = True

    if not isinstance(db.get("categories"), dict):
        db["categories"] = {FALLBACK_CATEGORY: {"color": DEFAULT_COLOR}}
        changed = True

    if not isinstance(db.get("prefs"), dict):
        db["prefs"] = {"default_category": FALLBACK_CATEGORY, "hide_default_category": False, "view_mode": "comfortable"}
        changed = True

    db.setdefault("version", 10)
    db["prefs"].setdefault("default_category", FALLBACK_CATEGORY)
    db["prefs"].setdefault("hide_default_category", False)
    db["prefs"].setdefault("view_mode", "comfortable")

    if not isinstance(db["prefs"].get("default_category"), str) or not db["prefs"]["default_category"].strip():
        db["prefs"]["default_category"] = FALLBACK_CATEGORY
        changed = True
    db["prefs"]["default_category"] = db["prefs"]["default_category"].strip()

    vm = (db["prefs"].get("view_mode") or "comfortable").strip().lower()
    if vm not in ("comfortable", "compact"):
        db["prefs"]["view_mode"] = "comfortable"
        changed = True
    else:
        db["prefs"]["view_mode"] = vm

    for cat, meta in list(db["categories"].items()):
        if not isinstance(meta, dict):
            db["categories"][cat] = {"color": DEFAULT_COLOR}
            changed = True
        else:
            if not meta.get("color") or not isinstance(meta.get("color"), str):
                meta["color"] = DEFAULT_COLOR
                changed = True
            meta["color"] = meta["color"].strip() or DEFAULT_COLOR

    default_cat = db["prefs"]["default_category"]
    if default_cat not in db["categories"]:
        db["categories"][default_cat] = {"color": DEFAULT_COLOR}
        changed = True

    normalized_links: List[Dict[str, Any]] = []
    for row in db["links"]:
        if not isinstance(row, dict):
            changed = True
            continue

        name = (row.get("name") or "").strip()
        url = (row.get("url") or "").strip()
        if not name or not url:
            changed = True
            continue

        if not row.get("id"):
            row["id"] = str(uuid.uuid4())
            changed = True

        cat = _normalize_category_name(row.get("category") or "")
        if not cat:
            cat = db["prefs"]["default_category"]

        if row.get("category") != cat:
            row["category"] = cat
            changed = True

        row.setdefault("info", "")
        row.setdefault("created", _now_iso())
        row.setdefault("updated", row.get("created", _now_iso()))

        if cat not in db["categories"]:
            db["categories"][cat] = {"color": DEFAULT_COLOR}
            changed = True
        if not isinstance(db["categories"][cat], dict):
            db["categories"][cat] = {"color": DEFAULT_COLOR}
            changed = True
        db["categories"][cat].setdefault("color", DEFAULT_COLOR)

        normalized_links.append(row)

    if normalized_links != db["links"]:
        db["links"] = normalized_links
        changed = True

    if changed:
        save_db(db)

    return db


def _counts_by_cat(db: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    default_cat = (db.get("prefs", {}).get("default_category") or FALLBACK_CATEGORY).strip() or FALLBACK_CATEGORY
    for r in db.get("links", []):
        if not isinstance(r, dict):
            continue
        c = _normalize_category_name(r.get("category") or "") or default_cat
        counts[c] = counts.get(c, 0) + 1
    return counts


def _categories(db: Dict[str, Any], hide_default: bool) -> List[str]:
    cats = set()
    default_cat = (db.get("prefs", {}).get("default_category") or FALLBACK_CATEGORY).strip() or FALLBACK_CATEGORY

    for r in db.get("links", []):
        if isinstance(r, dict):
            c = _normalize_category_name(r.get("category") or "") or default_cat
            cats.add(c)

    if isinstance(db.get("categories"), dict):
        cats.update(db["categories"].keys())

    out = sorted(cats, key=lambda x: x.lower())
    if hide_default and default_cat in out:
        out.remove(default_cat)
    return out


def _get_useful_links_config(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Per-tool config uit settings.json (root of modules.useful_links).
    """
    cfg = cynit_theme.get_module_cfg(settings, "useful_links")

    def _mode_defaults(name: str) -> Dict[str, Any]:
        if name == "compact":
            return {
                "min_width": 240,
                "gap": 10,
                "card_padding_y": 8,
                "card_padding_x": 10,
                "breakpoints": [(1400, 5), (1600, 6), (1900, 7)],
                "max_columns": 7,
            }
        return {
            "min_width": 280,
            "gap": 14,
            "card_padding_y": 10,
            "card_padding_x": 12,
            "breakpoints": [(1400, 4), (1600, 5), (1900, 6)],
            "max_columns": 6,
        }

    out: Dict[str, Any] = {"default_mode": "comfortable", "modes": {}}
    if isinstance(cfg.get("default_mode"), str) and cfg["default_mode"].strip().lower() in ("comfortable", "compact"):
        out["default_mode"] = cfg["default_mode"].strip().lower()

    modes = cfg.get("modes") if isinstance(cfg.get("modes"), dict) else {}
    for mode_name in ("comfortable", "compact"):
        m = modes.get(mode_name, {}) if isinstance(modes.get(mode_name), dict) else {}
        d = _mode_defaults(mode_name)

        min_width = int(m.get("min_width", d["min_width"]))
        gap = int(m.get("gap", d["gap"]))
        pad_y = int(m.get("card_padding_y", d["card_padding_y"]))
        pad_x = int(m.get("card_padding_x", d["card_padding_x"]))
        max_cols = int(m.get("max_columns", d["max_columns"]))

        bp_raw = m.get("breakpoints", d["breakpoints"])
        bps: List[Tuple[int, int]] = []
        if isinstance(bp_raw, list):
            for item in bp_raw:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    try:
                        bps.append((int(item[0]), int(item[1])))
                    except Exception:
                        pass
        if not bps:
            bps = list(d["breakpoints"])

        out["modes"][mode_name] = {
            "min_width": max(180, min_width),
            "gap": max(6, gap),
            "card_padding_y": max(6, pad_y),
            "card_padding_x": max(8, pad_x),
            "breakpoints": bps,
            "max_columns": max(1, min(12, max_cols)),
        }

    return out


TEMPLATE = r"""
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>Nuttige links - CyNiT Tools</title>
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <style>
    {{ base_css|safe }}
    {{ extra_css|safe }}
  </style>
</head>

<body class="mode-{{ view_mode|e }}">
  {{ header|safe }}

  <div class="page">
    <h1>Nuttige links</h1>

    {% if error %}
      <div class="err">{{ error }}</div>
    {% endif %}
    {% if msg %}
      <div class="ok">{{ msg }}</div>
    {% endif %}

    <!-- TOP BAR: Tabs + View toggle -->
    <div class="topbar sticky-tabs">
      <div class="tabs">
        <button id="tab-links" class="tabbtn" type="button">Links</button>
        <button id="tab-manage" class="tabbtn" type="button">Beheer</button>
      </div>

      <div class="viewtoggle" role="group" aria-label="Weergave">
        <form method="post" action="/links/prefs" style="display:flex; gap:8px; margin:0;">
          <input type="hidden" name="action" value="set_view_mode">
          <input type="hidden" name="view_mode" value="comfortable">
          <input type="hidden" name="cat" value="{{ active_cat }}">
          <button type="submit" class="pill {% if view_mode=='comfortable' %}active{% endif %}" title="Comfortabel">
            Comfortabel
          </button>
        </form>
        <form method="post" action="/links/prefs" style="display:flex; gap:8px; margin:0;">
          <input type="hidden" name="action" value="set_view_mode">
          <input type="hidden" name="view_mode" value="compact">
          <input type="hidden" name="cat" value="{{ active_cat }}">
          <button type="submit" class="pill {% if view_mode=='compact' %}active{% endif %}" title="Compact">
            Compact
          </button>
        </form>
      </div>
    </div>

    <!-- CATEGORIE FILTERS (BLOKKEN) -->
    <div class="catbar" id="links">
      {% for c in categories %}
        <a
          class="catblock {% if c == active_cat %}active{% endif %}"
          href="/links?cat={{ c|urlencode }}#links"
          style="border-left: 6px solid {{ cat_colors.get(c, colors.button_fg) }};"
        >
          <div class="catname">{{ c }}</div>
          <div class="catcount">{{ counts.get(c, 0) }} link(s)</div>
        </a>
      {% endfor %}

      <a
        class="catblock {% if active_cat == '__ALL__' %}active{% endif %}"
        href="/links?cat=__ALL__#links"
        style="border-left: 6px solid {{ colors.button_fg }};"
      >
        <div class="catname">Alle</div>
        <div class="catcount">{{ total }} link(s)</div>
      </a>
    </div>

    <!-- PANEL 1: LINKS -->
    <div id="panel-links">
      {% if filtered %}
        <div class="grid">
          {% for r in filtered %}
            {% set cc = cat_colors.get(r.category, colors.button_fg) %}
            <div class="card"
                 data-link-card="1"
                 data-id="{{ r.id|e }}"
                 data-name="{{ r.name|e }}"
                 data-url="{{ r.url|e }}"
                 data-category="{{ r.category|e }}"
                 data-info="{{ (r.info or '')|e }}"
                 style="border-left: 6px solid {{ cc }}; --catcolor: {{ cc }};">
              <div class="card-title">
                <div class="card-name">{{ r.name }}</div>

                <div class="actions">
                  <button type="button" class="iconbtn" title="Bewerk" data-edit-btn="1">✏️</button>
                  <button type="button" class="iconbtn" title="Copy" data-copy-btn="1" data-copy="{{ r.url|e }}">✔️</button>

                  <form method="post" action="/links/delete/{{ r.id }}"
                        style="display:inline-block; margin:0;"
                        onsubmit="return confirm('Verwijderen?');">
                    <input type="hidden" name="cat" value="{{ active_cat }}">
                    <button type="submit" class="iconbtn" title="Verwijder">🗑️</button>
                  </form>
                </div>
              </div>

              <div class="hint">Categorie: <strong>{{ r.category }}</strong></div>

              <div style="margin-top:6px;">
                <a class="url" href="{{ r.url }}" target="_blank" rel="noopener noreferrer">
                  {{ r.url }}
                </a>
              </div>

              {% if r.info %}
                <div class="meta">{{ r.info }}</div>
              {% else %}
                <div class="meta muted">&nbsp;</div>
              {% endif %}
            </div>
          {% endfor %}
        </div>
      {% else %}
        <p>Geen links in deze categorie.</p>
      {% endif %}
    </div>

    <!-- PANEL 2: BEHEER -->
    <div id="panel-manage" style="display:none;">
      <h2>Nieuwe link toevoegen</h2>
      <p class="hint">Naam en URL zijn verplicht. Categorie leeg = default category.</p>

      <form method="post" action="/links/add">
        <div class="row">
          <div>Naam *</div>
          <div><input type="text" name="name" required></div>
        </div>

        <div class="row">
          <div>URL *</div>
          <div><input type="text" name="url" required placeholder="https://..."></div>
        </div>

        <div class="row">
          <div>Categorie</div>
          <div>
            <input type="text" name="category" list="catlist" placeholder="(leeg = default)">
            <datalist id="catlist">
              {% for c in all_categories %}<option value="{{ c }}"></option>{% endfor %}
            </datalist>
            <div class="hint">Default: <strong>{{ prefs.default_category }}</strong></div>
          </div>
        </div>

        <div class="row">
          <div>Info</div>
          <div><textarea name="info" placeholder="Extra uitleg (optioneel)"></textarea></div>
        </div>

        <button type="submit">➕ Toevoegen</button>
      </form>

      <hr class="sep" id="manage">

      <div class="prefsbar">
        <h3 style="margin:0 0 10px 0;">Voorkeuren</h3>

        <form method="post" action="/links/prefs"
              style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:10px;">
          <input type="hidden" name="action" value="set_default_category">
          <label style="display:flex; gap:10px; align-items:center;">
            <span>Default category</span>
            <select name="default_category" class="selectbox">
              {% for c in all_categories %}
                <option value="{{ c }}" {% if c == prefs.default_category %}selected{% endif %}>{{ c }}</option>
              {% endfor %}
            </select>
          </label>
          <button type="submit" class="smallbtn">Opslaan</button>
          <span class="hint">Lege categorie bij toevoegen/edit gaat naar deze default.</span>
        </form>

        <form method="post" action="/links/prefs"
              style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
          <input type="hidden" name="action" value="toggle_hide_default">
          <label style="display:flex; gap:10px; align-items:center; cursor:pointer;">
            <input type="checkbox" name="hide_default_category" value="1" {% if prefs.hide_default_category %}checked{% endif %}>
            <span>Sleep/Hide default category (“{{ prefs.default_category }}”)</span>
          </label>
          <button type="submit" class="smallbtn">Opslaan</button>
        </form>
      </div>

      <hr class="sep">

      <div class="prefsbar">
        <h3 style="margin:0 0 10px 0;">Grid kolommen (instelling in settings.json)</h3>
        <p class="hint" style="margin-top:0;">
          Dit schrijft naar <code>config/settings.json</code> → <code>useful_links.modes.&lt;mode&gt;.max_columns</code>.
        </p>

        <form method="post" action="/links/settings/grid" style="display:flex; flex-direction:column; gap:12px; margin:0;">
          <input type="hidden" name="return_tab" value="manage">

          <div class="gridrow">
            <div class="gridlabel"><strong>Comfortabel</strong></div>
            <div class="gridcontrol">
              <input type="range" name="max_columns_comfortable" min="1" max="12" value="{{ max_cols_comfortable }}" oninput="document.getElementById('mc_c').textContent=this.value;">
              <div class="gridvalue"><span id="mc_c">{{ max_cols_comfortable }}</span> kolommen (max)</div>
            </div>
          </div>

          <div class="gridrow">
            <div class="gridlabel"><strong>Compact</strong></div>
            <div class="gridcontrol">
              <input type="range" name="max_columns_compact" min="1" max="12" value="{{ max_cols_compact }}" oninput="document.getElementById('mc_k').textContent=this.value;">
              <div class="gridvalue"><span id="mc_k">{{ max_cols_compact }}</span> kolommen (max)</div>
            </div>
          </div>

          <div>
            <button type="submit" class="smallbtn">💾 Opslaan in settings.json</button>
          </div>
        </form>
      </div>

      <hr class="sep">

      <h2>Categoriebeheer</h2>
      <p class="hint">Dubbelklik op de naam om te hernoemen (of gebruik ✏️).</p>

      <div style="margin-top:14px;">
        <h3 style="margin:0 0 8px 0;">Bestaande categorieën</h3>

        {% for c in all_categories %}
          <div class="catrow"
               data-cat="{{ c|e }}"
               data-color="{{ cat_colors.get(c, colors.button_fg)|e }}"
               data-isdefault="{{ '1' if c == prefs.default_category else '0' }}">
            <div class="swatch" style="background: {{ cat_colors.get(c, colors.button_fg) }};"></div>

            <div class="catlabel" data-catlabel="1" title="Dubbelklik om te hernoemen">
              <strong>{{ c }}</strong>
              {% if c == prefs.default_category %}
                <span class="badge">DEFAULT</span>
              {% endif %}
            </div>

            <form method="post" action="/links/category/color" style="display:flex; gap:8px; align-items:center;">
              <input type="hidden" name="category" value="{{ c }}">
              <input type="color" name="color" value="{{ cat_colors.get(c, colors.button_fg) }}" title="Kleur">
              <button type="submit" class="iconbtn" title="Kleur opslaan">💾</button>
            </form>

            <button type="button" class="iconbtn" title="Hernoem categorie" data-rename-btn="1">✏️</button>

            <form method="post" action="/links/category/delete"
                  style="margin-left:auto;"
                  onsubmit="return confirm('Categorie verwijderen?');">
              <input type="hidden" name="category" value="{{ c }}">
              <button type="submit" class="iconbtn" title="Categorie verwijderen">🗑️</button>
            </form>
          </div>
        {% endfor %}
      </div>
    </div>

    <!-- EDIT LINK MODAL -->
    <div id="edit_modal" class="modal" style="display:none;">
      <div class="modalbox" role="dialog" aria-modal="true" aria-label="Link bewerken">
        <h2>Link bewerken</h2>

        <form method="post" action="/links/update">
          <input type="hidden" id="edit_id" name="id">

          <div class="row">
            <div>Naam *</div>
            <div><input type="text" id="edit_name" name="name" required></div>
          </div>

          <div class="row">
            <div>URL *</div>
            <div><input type="text" id="edit_url" name="url" required></div>
          </div>

          <div class="row">
            <div>Categorie</div>
            <div>
              <input type="text" id="edit_category" name="category" list="catlist" placeholder="(leeg = default)">
              <div class="hint">Default: <strong>{{ prefs.default_category }}</strong></div>
            </div>
          </div>

          <div class="row">
            <div>Info</div>
            <div><textarea id="edit_info" name="info"></textarea></div>
          </div>

          <div class="modalactions">
            <button type="submit">💾 Opslaan</button>
            <button type="button" data-close-edit="1">Annuleren</button>
          </div>
        </form>
      </div>
    </div>

    <!-- RENAME CATEGORY MODAL -->
    <div id="rename_modal" class="modal" style="display:none;">
      <div class="modalbox" role="dialog" aria-modal="true" aria-label="Categorie hernoemen">
        <div class="rename-preview">
          <div id="rename_preview_bar" class="rename-preview-bar"></div>
          <div class="rename-preview-text">
            <div class="rename-preview-title">
              <span id="rename_preview_name"></span>
              <span id="rename_preview_tag" class="badge" style="display:none;">DEFAULT</span>
            </div>
            <div class="hint">Live preview</div>
          </div>
        </div>

        <h2 style="margin-top:12px;">Categorie hernoemen</h2>

        <form method="post" action="/links/category/rename">
          <input type="hidden" id="rename_old" name="old_category">

          <div class="row">
            <div>Nieuwe naam *</div>
            <div><input type="text" id="rename_new" name="new_category" required></div>
          </div>

          <div class="row">
            <div>Kleur</div>
            <div>
              <input type="color" id="rename_color" name="color" value="#00f700">
              <div class="hint">Kleur wordt opgeslagen op de nieuwe categorie (of overschrijft).</div>
            </div>
          </div>

          <div class="row">
            <div>Links</div>
            <div>
              <label style="display:flex; gap:10px; align-items:center; cursor:pointer;">
                <input type="checkbox" id="rename_move" name="move_links" value="1" checked>
                <span>Move links van oude categorie naar nieuwe categorie</span>
              </label>
            </div>
          </div>

          <div class="modalactions">
            <button type="submit">✅ Hernoem</button>
            <button type="button" data-close-rename="1">Annuleren</button>
          </div>
        </form>
      </div>
    </div>

  </div>

  {{ footer|safe }}

  <script>
    function isVisible(el) { return el && el.style && el.style.display !== 'none'; }

    function getFocusable(container) {
      if (!container) return [];
      const selectors = [
        'a[href]','button:not([disabled])','textarea:not([disabled])',
        'input:not([disabled])','select:not([disabled])','[tabindex]:not([tabindex="-1"])'
      ];
      return Array.from(container.querySelectorAll(selectors.join(',')))
        .filter(el => el.offsetParent !== null);
    }

    function trapTab(container, ev) {
      if (ev.key !== 'Tab') return;
      const focusables = getFocusable(container);
      if (focusables.length === 0) return;

      const first = focusables[0];
      const last = focusables[focusables.length - 1];

      if (ev.shiftKey) {
        if (document.activeElement === first) { ev.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last) { ev.preventDefault(); first.focus(); }
      }
    }

    async function copyText(text) {
      try { await navigator.clipboard.writeText(text); }
      catch (e) {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
    }

    function setTab(which) {
      const pLinks = document.getElementById('panel-links');
      const pManage = document.getElementById('panel-manage');
      const tLinks = document.getElementById('tab-links');
      const tManage = document.getElementById('tab-manage');

      if (which === 'manage') {
        pLinks.style.display = 'none';
        pManage.style.display = 'block';
        tLinks.classList.remove('active');
        tManage.classList.add('active');
        location.hash = '#manage';
      } else {
        pLinks.style.display = 'block';
        pManage.style.display = 'none';
        tManage.classList.remove('active');
        tLinks.classList.add('active');
        location.hash = '#links';
      }
    }

    function openEditFromCard(cardEl) {
      document.getElementById('edit_id').value = cardEl.dataset.id || '';
      document.getElementById('edit_name').value = cardEl.dataset.name || '';
      document.getElementById('edit_url').value = cardEl.dataset.url || '';
      document.getElementById('edit_category').value = cardEl.dataset.category || '';
      document.getElementById('edit_info').value = cardEl.dataset.info || '';
      const m = document.getElementById('edit_modal');
      m.style.display = 'flex';
      setTimeout(() => document.getElementById('edit_name').focus(), 0);
    }

    function closeEdit() {
      const m = document.getElementById('edit_modal');
      if (m) m.style.display = 'none';
    }

    function updateRenamePreview(name, color, isDefault) {
      document.getElementById('rename_preview_name').textContent = (name || '').toString();
      document.getElementById('rename_preview_bar').style.background = color || '#00f700';
      document.getElementById('rename_preview_tag').style.display = isDefault ? 'inline-block' : 'none';
    }

    function openRename(cat, color, isDefault) {
      document.getElementById('rename_old').value = cat;
      document.getElementById('rename_new').value = cat;
      const cp = document.getElementById('rename_color');
      cp.value = color || '#00f700';
      document.getElementById('rename_move').checked = true;
      updateRenamePreview(cat, cp.value, isDefault);

      const m = document.getElementById('rename_modal');
      m.style.display = 'flex';
      setTimeout(() => document.getElementById('rename_new').focus(), 0);
    }

    function closeRename() {
      const m = document.getElementById('rename_modal');
      if (m) m.style.display = 'none';
    }

    function closeAllModals() { closeEdit(); closeRename(); }

    function modalKeyHandler(ev) {
      const editModal = document.getElementById('edit_modal');
      const renameModal = document.getElementById('rename_modal');

      const editOpen = isVisible(editModal);
      const renameOpen = isVisible(renameModal);
      const anyOpen = editOpen || renameOpen;

      if (ev.key === 'Escape' && anyOpen) { ev.preventDefault(); closeAllModals(); return; }

      if ((ev.ctrlKey || ev.metaKey) && (ev.key === 'w' || ev.key === 'W') && anyOpen) {
        ev.preventDefault(); closeAllModals(); return;
      }

      if ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter') {
        if (editOpen) { const f = editModal.querySelector('form'); if (f) { ev.preventDefault(); f.requestSubmit ? f.requestSubmit() : f.submit(); } return; }
        if (renameOpen) { const f = renameModal.querySelector('form'); if (f) { ev.preventDefault(); f.requestSubmit ? f.requestSubmit() : f.submit(); } return; }
      }

      if ((ev.ctrlKey || ev.metaKey) && (ev.key === 's' || ev.key === 'S')) {
        if (editOpen) { const f = editModal.querySelector('form'); if (f) { ev.preventDefault(); f.requestSubmit ? f.requestSubmit() : f.submit(); } return; }
        if (renameOpen) { const f = renameModal.querySelector('form'); if (f) { ev.preventDefault(); f.requestSubmit ? f.requestSubmit() : f.submit(); } return; }
      }

      if (ev.key === 'Enter' && anyOpen) {
        const tag = ev.target?.tagName?.toLowerCase();
        if (tag !== 'button') { ev.preventDefault(); return; }
      }

      if (editOpen) trapTab(editModal.querySelector('.modalbox'), ev);
      else if (renameOpen) trapTab(renameModal.querySelector('.modalbox'), ev);
    }

    function bindModalOverlayClose(modalId) {
      const modal = document.getElementById(modalId);
      if (!modal) return;
      modal.addEventListener('mousedown', (ev) => { if (ev.target === modal) closeAllModals(); });
    }

    window.addEventListener('load', () => {
      document.getElementById('tab-links').addEventListener('click', () => setTab('links'));
      document.getElementById('tab-manage').addEventListener('click', () => setTab('manage'));

      if ((location.hash || '').toLowerCase().includes('manage')) setTab('manage');
      else setTab('links');

      document.querySelectorAll('[data-link-card="1"]').forEach(card => {
        card.addEventListener('dblclick', (ev) => {
          const t = ev.target;
          if (t.closest('a') || t.closest('button') || t.closest('form')) return;
          openEditFromCard(card);
        });

        const editBtn = card.querySelector('[data-edit-btn="1"]');
        if (editBtn) editBtn.addEventListener('click', (ev) => { ev.preventDefault(); ev.stopPropagation(); openEditFromCard(card); });

        const copyBtn = card.querySelector('[data-copy-btn="1"]');
        if (copyBtn) copyBtn.addEventListener('click', async (ev) => {
          ev.preventDefault(); ev.stopPropagation();
          await copyText(copyBtn.dataset.copy || card.dataset.url || '');
        });
      });

      document.querySelectorAll('[data-close-edit="1"]').forEach(btn => btn.addEventListener('click', closeEdit));
      document.querySelectorAll('[data-close-rename="1"]').forEach(btn => btn.addEventListener('click', closeRename));

      document.querySelectorAll('.catrow').forEach(row => {
        const cat = row.dataset.cat || '';
        const color = row.dataset.color || '#00f700';
        const isDefault = (row.dataset.isdefault || '0') === '1';

        const label = row.querySelector('[data-catlabel="1"]');
        if (label) label.addEventListener('dblclick', (ev) => { ev.preventDefault(); ev.stopPropagation(); openRename(cat, color, isDefault); });

        const pencil = row.querySelector('[data-rename-btn="1"]');
        if (pencil) pencil.addEventListener('click', (ev) => { ev.preventDefault(); ev.stopPropagation(); openRename(cat, color, isDefault); });
      });

      const rn = document.getElementById('rename_new');
      const rc = document.getElementById('rename_color');
      if (rn && rc) {
        const recompute = () => {
          const oldCat = document.getElementById('rename_old').value || '';
          const isDefault = document.getElementById('rename_preview_tag').style.display !== 'none';
          updateRenamePreview(rn.value || oldCat, rc.value, isDefault);
        };
        rn.addEventListener('input', recompute);
        rc.addEventListener('input', recompute);
      }

      bindModalOverlayClose('edit_modal');
      bindModalOverlayClose('rename_modal');
      document.addEventListener('keydown', modalKeyHandler);
    });
  </script>

  <script>
    {{ common_js|safe }}
  </script>
</body>
</html>
"""


def register_web_routes(app: Flask, settings: Dict[str, Any], tools=None) -> None:
    """
    settings wordt als fallback meegegeven, maar we lezen per request settings.json live,
    zodat je grid/tint/lettertypes meteen effect hebben zonder restart.
    """
    fallback_settings = settings if isinstance(settings, dict) else {}

    def _get_cat_colors(db: Dict[str, Any], colors: Dict[str, Any]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        if isinstance(db.get("categories"), dict):
            for k, v in db["categories"].items():
                if isinstance(v, dict):
                    out[k] = (v.get("color") or colors["button_fg"]).strip() or colors["button_fg"]
        return out

    def _css_for_mode(tool_cfg: Dict[str, Any], mode_name: str) -> str:
        mode = tool_cfg["modes"].get(mode_name) or tool_cfg["modes"]["comfortable"]
        minw = int(mode["min_width"])
        gap = int(mode["gap"])
        pad_y = int(mode["card_padding_y"])
        pad_x = int(mode["card_padding_x"])
        bps: List[Tuple[int, int]] = mode["breakpoints"]
        max_cols = int(mode.get("max_columns", 12))

        bp_css = ""
        for w, cols in bps:
            cols_eff = min(int(cols), max_cols)
            bp_css += f"""
            @media (min-width: {int(w)}px) {{
              body.mode-{mode_name} .grid {{ grid-template-columns: repeat({cols_eff}, 1fr); }}
            }}
            """

        return f"""
        body.mode-{mode_name} .grid {{
          grid-template-columns: repeat(auto-fill, minmax({minw}px, 1fr));
          gap: {gap}px;
        }}
        body.mode-{mode_name} .card {{
          padding: {pad_y}px {pad_x}px;
        }}
        {bp_css}
        """

    @app.route("/links", methods=["GET"])
    def useful_links_index():
        db = load_db()

        live_settings = cynit_theme.load_settings_live(fallback_settings)
        colors = live_settings["colors"]
        tool_cfg = _get_useful_links_config(live_settings)

        base_css = cynit_layout.common_css(live_settings)
        common_js = cynit_layout.common_js()
        header = cynit_layout.header_html(live_settings, tools=tools, title="Nuttige links", right_html="")
        footer = cynit_layout.footer_html()

        prefs = db.get("prefs", {}) if isinstance(db.get("prefs"), dict) else {}
        default_cat = (prefs.get("default_category") or FALLBACK_CATEGORY).strip() or FALLBACK_CATEGORY
        hide_default = bool(prefs.get("hide_default_category", False))

        view_mode = (prefs.get("view_mode") or "").strip().lower()
        if view_mode not in ("comfortable", "compact"):
            view_mode = tool_cfg.get("default_mode", "comfortable")

        counts = _counts_by_cat(db)
        total = len(db.get("links", []))

        categories = _categories(db, hide_default=hide_default)
        all_categories = _categories(db, hide_default=False)

        active_cat = (request.args.get("cat") or "__ALL__").strip() or "__ALL__"
        cat_colors = _get_cat_colors(db, colors)

        rows = db.get("links", [])
        rows = sorted(rows, key=lambda r: ((r.get("category") or "").lower(), (r.get("name") or "").lower()))

        if active_cat != "__ALL__":
            filtered = [r for r in rows if (r.get("category") or "") == active_cat]
        else:
            filtered = [r for r in rows if (r.get("category") or "") != default_cat] if hide_default else rows

        extra_css = f"""
        .topbar {{
          display:flex; align-items:center; justify-content:space-between; gap:10px;
          margin: 8px 0 14px 0;
        }}

        .sticky-tabs {{
          position: sticky;
          top: 0;
          z-index: 50;
          padding: 8px 0;
          background: {colors.get("background", "#000")};
          border-bottom: 1px solid #222;
        }}

        .tabs {{ display:flex; gap:8px; }}
        .tabbtn {{
          border: 1px solid #333;
          background: #111;
          border-radius: 0;
          padding: 6px 12px;
          cursor: pointer;
          color: {colors["general_fg"]};
        }}
        .tabbtn.active {{
          background: {colors["button_fg"]};
          color: #000;
          border-color: {colors["button_fg"]};
          font-weight: 800;
        }}

        .viewtoggle {{ display:flex; gap:8px; align-items:center; }}
        .pill {{
          border: 1px solid #333; background:#111; color:{colors["general_fg"]};
          border-radius: 0; padding: 6px 10px; cursor:pointer;
        }}
        .pill:hover {{ background:#222; }}
        .pill.active {{
          background: {colors["button_fg"]};
          color: #000;
          border-color: {colors["button_fg"]};
          font-weight: 800;
        }}

        .catbar {{ display:flex; flex-wrap:wrap; gap:10px; margin:10px 0 16px 0; }}
        .catblock {{
          display:flex; flex-direction:column; justify-content:center; gap:2px;
          width: 160px; min-height: 58px; padding: 10px 12px;
          border: 1px solid #2a2a2a; border-radius: 0; background: #0b0b0b;
          text-decoration:none; color: {colors["general_fg"]};
          transition: background 0.15s ease, border-color 0.15s ease, transform 0.05s ease;
        }}
        .catblock:hover {{ background:#101010; }}
        .catblock:active {{ transform: translateY(1px); }}
        .catblock.active {{ background:#111; border-color:#ffffff55; }}
        .catname {{ font-weight: 800; line-height: 1.05; }}
        .catcount {{ opacity: 0.85; font-size: 0.9em; }}

        .grid {{
          display: grid;
          margin-bottom: 18px;
        }}

        .card {{
          border: 1px solid #2a2a2a; border-radius: 0; background: #0b0b0b;
          display:flex; flex-direction:column; height: 100%;
          transition: background 0.15s ease, border-color 0.15s ease;
        }}
        .card:hover {{ background:#101010; border-color: {colors["button_fg"]}; }}

        .card-title {{
          display:flex; justify-content:space-between; align-items:center; gap:8px;
          margin:0 0 8px 0; padding-bottom:8px; border-bottom:1px solid #222;
        }}

        /* ✅ Link-naam in categorie-kleur */
        .card-name {{
          font-weight: 800;
          letter-spacing: 0.2px;
          color: var(--catcolor, {colors["general_fg"]});
        }}

        .actions {{ display: inline-flex; gap: 6px; align-items: center; }}
        .iconbtn {{
          border: 1px solid #333; background: #111; border-radius: 0;
          padding: 4px 8px; cursor: pointer; color: {colors["general_fg"]};
        }}
        .iconbtn:hover {{ background: #222; }}

        .url {{ word-break: break-all; text-decoration: underline; color: {colors["general_fg"]}; }}

        .meta {{ white-space: pre-wrap; margin-top: auto; padding-top: 10px; opacity: 0.95; }}
        .muted {{ opacity: 0.5; }}

        .row {{
          display:grid; grid-template-columns: 160px 1fr; gap:10px;
          align-items:center; margin: 8px 0;
        }}

        input[type="text"], textarea {{
          width: 100%; padding: 7px 10px; border-radius: 0; border: 1px solid #333;
          background: #0b0b0b; color: {colors["general_fg"]}; box-sizing: border-box;
        }}
        textarea {{ min-height: 90px; resize: vertical; }}

        input[type="color"] {{
          width: 54px; height: 34px; border: 1px solid #333; background: #111;
          padding: 0; border-radius: 0; cursor: pointer;
        }}

        input[type="range"] {{
          width: min(520px, 100%);
        }}

        .selectbox {{
          border: 1px solid #333; background: #0b0b0b; color: {colors["general_fg"]};
          border-radius: 0; padding: 6px 10px; min-width: 240px;
        }}

        .hint {{ opacity: 0.85; font-size: 0.9em; }}
        .err {{ color: #ff4d4d; font-weight: bold; margin: 8px 0 10px 0; }}
        .ok {{ color: #88ff88; font-weight: bold; margin: 8px 0 10px 0; }}

        .sep {{ margin: 18px 0; border: 0; border-top: 1px solid #222; }}

        .prefsbar {{ border: 1px solid #222; background: #0b0b0b; padding: 10px 12px; border-radius: 0; }}
        .smallbtn {{
          border: 1px solid #333; background: #111; border-radius: 0;
          padding: 6px 10px; cursor: pointer; color: {colors["general_fg"]};
        }}
        .smallbtn:hover {{ background: #222; }}

        .gridrow {{
          display:grid; grid-template-columns: 160px 1fr; gap: 10px; align-items:center;
          padding: 8px 0; border-top: 1px solid #1b1b1b;
        }}
        .gridrow:first-child {{ border-top: 0; }}
        .gridlabel {{ opacity: 0.95; }}
        .gridcontrol {{ display:flex; align-items:center; gap: 12px; flex-wrap: wrap; }}
        .gridvalue {{ opacity: 0.9; min-width: 160px; }}

        .catrow {{
          display:flex; gap:10px; align-items:center; margin:6px 0;
          border: 1px solid #222; background:#0b0b0b; padding: 8px 10px; border-radius: 0;
        }}
        .swatch {{ width:14px; height:14px; border-radius:0; border: 1px solid #222; }}

        .catlabel {{
          min-width: 260px; display:flex; gap:10px; align-items:center;
          cursor: default; user-select: none;
        }}
        .catlabel:hover {{ outline: 1px dashed #333; outline-offset: 3px; }}

        .badge {{
          display:inline-block; padding: 2px 6px; border: 1px solid #333;
          background: #111; border-radius: 0; font-size: 0.75em; opacity: 0.9;
        }}

        .modal {{
          position:fixed; inset:0; background: rgba(0,0,0,0.75);
          display:flex; align-items:flex-start; justify-content:center;
          padding: 6vh 12px; z-index: 9999;
        }}
        .modalbox {{
          width: min(880px, 100%); background:#0b0b0b; border:1px solid #333;
          border-radius:0; padding: 14px 16px;
        }}
        .modalactions {{ margin-top: 12px; display:flex; gap:10px; }}

        .rename-preview {{ display:flex; gap:12px; align-items:stretch; border:1px solid #222; background:#0b0b0b; }}
        .rename-preview-bar {{ width: 10px; background: {colors["button_fg"]}; }}
        .rename-preview-text {{ padding: 10px 12px; flex: 1; }}
        .rename-preview-title {{ font-weight: 800; display:flex; gap:10px; align-items:center; }}

        {_css_for_mode(tool_cfg, "comfortable")}
        {_css_for_mode(tool_cfg, "compact")}
        """

        max_cols_comfortable = int(tool_cfg["modes"]["comfortable"].get("max_columns", 6))
        max_cols_compact = int(tool_cfg["modes"]["compact"].get("max_columns", 7))

        return render_template_string(
            TEMPLATE,
            base_css=base_css,
            extra_css=extra_css,
            common_js=common_js,
            header=header,
            footer=footer,
            colors=colors,
            categories=categories,
            all_categories=all_categories,
            counts=counts,
            total=total,
            active_cat=active_cat,
            filtered=filtered,
            cat_colors=cat_colors,
            prefs={"default_category": default_cat, "hide_default_category": hide_default},
            view_mode=view_mode,
            max_cols_comfortable=max_cols_comfortable,
            max_cols_compact=max_cols_compact,
            error=request.args.get("error", ""),
            msg=request.args.get("msg", ""),
        )

    # ---- LINKS CRUD ----
    @app.route("/links/add", methods=["POST"])
    def useful_links_add():
        db = load_db()
        default_cat = db["prefs"]["default_category"]

        name = (request.form.get("name") or "").strip()
        url = (request.form.get("url") or "").strip()
        category = _normalize_category_name(request.form.get("category") or "")
        info = (request.form.get("info") or "").strip()

        if not name or not url:
            return redirect(url_for("useful_links_index", cat="__ALL__", error="Naam en URL zijn verplicht.") + "#manage")

        if not category:
            category = default_cat

        db["categories"].setdefault(category, {"color": DEFAULT_COLOR})
        if not isinstance(db["categories"][category], dict):
            db["categories"][category] = {"color": DEFAULT_COLOR}
        db["categories"][category].setdefault("color", DEFAULT_COLOR)

        db["links"].append(
            {"id": str(uuid.uuid4()), "name": name, "url": url, "category": category, "info": info,
             "created": _now_iso(), "updated": _now_iso()}
        )
        save_db(db)
        return redirect(url_for("useful_links_index", cat=category, msg="Link toegevoegd!") + "#links")

    @app.route("/links/update", methods=["POST"])
    def useful_links_update():
        db = load_db()
        default_cat = db["prefs"]["default_category"]

        rid = (request.form.get("id") or "").strip()
        name = (request.form.get("name") or "").strip()
        url = (request.form.get("url") or "").strip()
        category = _normalize_category_name(request.form.get("category") or "")
        info = (request.form.get("info") or "").strip()

        if not rid or not name or not url:
            return redirect(url_for("useful_links_index", cat="__ALL__", error="ID, Naam en URL zijn verplicht.") + "#links")

        if not category:
            category = default_cat

        db["categories"].setdefault(category, {"color": DEFAULT_COLOR})
        if not isinstance(db["categories"][category], dict):
            db["categories"][category] = {"color": DEFAULT_COLOR}
        db["categories"][category].setdefault("color", DEFAULT_COLOR)

        found = False
        for r in db.get("links", []):
            if r.get("id") == rid:
                r["name"] = name
                r["url"] = url
                r["category"] = category
                r["info"] = info
                r["updated"] = _now_iso()
                found = True
                break

        if not found:
            return redirect(url_for("useful_links_index", cat="__ALL__", error="Link niet gevonden.") + "#links")

        save_db(db)
        return redirect(url_for("useful_links_index", cat=category, msg="Link aangepast!") + "#links")

    @app.route("/links/delete/<rid>", methods=["POST"])
    def useful_links_delete(rid: str):
        db = load_db()
        cat = (request.form.get("cat") or "__ALL__").strip() or "__ALL__"

        before = len(db.get("links", []))
        db["links"] = [r for r in db.get("links", []) if r.get("id") != rid]
        after = len(db["links"])
        save_db(db)

        msg = "Link verwijderd!" if after < before else "Link niet gevonden."
        return redirect(url_for("useful_links_index", cat=cat, msg=msg) + "#links")

    # ---- PREFS ----
    @app.route("/links/prefs", methods=["POST"])
    def useful_links_prefs():
        db = load_db()
        action = (request.form.get("action") or "").strip()

        if action == "toggle_hide_default":
            hide_default = bool(request.form.get("hide_default_category"))
            db["prefs"]["hide_default_category"] = hide_default
            save_db(db)
            return redirect(url_for("useful_links_index", cat="__ALL__", msg="Voorkeuren opgeslagen!") + "#manage")

        if action == "set_default_category":
            new_default = _normalize_category_name(request.form.get("default_category") or "")
            if not new_default:
                return redirect(url_for("useful_links_index", cat="__ALL__", error="Default category is verplicht.") + "#manage")

            db["prefs"]["default_category"] = new_default
            db.setdefault("categories", {})
            db["categories"].setdefault(new_default, {"color": DEFAULT_COLOR})
            if not isinstance(db["categories"][new_default], dict):
                db["categories"][new_default] = {"color": DEFAULT_COLOR}
            db["categories"][new_default].setdefault("color", DEFAULT_COLOR)

            save_db(db)
            return redirect(url_for("useful_links_index", cat="__ALL__", msg="Default category opgeslagen!") + "#manage")

        if action == "set_view_mode":
            vm = (request.form.get("view_mode") or "").strip().lower()
            if vm not in ("comfortable", "compact"):
                return redirect(url_for("useful_links_index", cat="__ALL__", error="Onbekende view mode.") + "#links")
            db["prefs"]["view_mode"] = vm
            save_db(db)
            cat = (request.form.get("cat") or "__ALL__").strip() or "__ALL__"
            return redirect(url_for("useful_links_index", cat=cat, msg="Weergave aangepast!") + "#links")

        return redirect(url_for("useful_links_index", cat="__ALL__", error="Onbekende actie.") + "#manage")

    # ---- SETTINGS: GRID SLIDERS (write settings.json) ----
    @app.route("/links/settings/grid", methods=["POST"])
    def useful_links_settings_grid():
        live_settings = cynit_theme.load_settings_live(fallback_settings)

        try:
            mc_c = int(request.form.get("max_columns_comfortable", "6"))
            mc_k = int(request.form.get("max_columns_compact", "7"))
        except Exception:
            return redirect(url_for("useful_links_index", cat="__ALL__", error="Ongeldige slider waarde.") + "#manage")

        mc_c = max(1, min(12, mc_c))
        mc_k = max(1, min(12, mc_k))

        # Schrijf altijd op root "useful_links" (cynit_theme.get_module_cfg leest dit ook)
        live_settings.setdefault("useful_links", {})
        if not isinstance(live_settings["useful_links"], dict):
            live_settings["useful_links"] = {}

        ul = live_settings["useful_links"]
        ul.setdefault("modes", {})
        if not isinstance(ul["modes"], dict):
            ul["modes"] = {}

        for mode_name, val in (("comfortable", mc_c), ("compact", mc_k)):
            ul["modes"].setdefault(mode_name, {})
            if not isinstance(ul["modes"][mode_name], dict):
                ul["modes"][mode_name] = {}
            ul["modes"][mode_name]["max_columns"] = val

        if not cynit_theme.save_settings(live_settings):
            return redirect(url_for("useful_links_index", cat="__ALL__", error="Kon settings.json niet schrijven.") + "#manage")

        return redirect(url_for("useful_links_index", cat="__ALL__", msg="Grid-instelling opgeslagen in settings.json!") + "#manage")

    # ---- CATEGORY COLOR ----
    @app.route("/links/category/color", methods=["POST"])
    def useful_links_category_color():
        db = load_db()
        cat = _normalize_category_name(request.form.get("category") or "")
        color = (request.form.get("color") or "").strip()

        if not cat:
            return redirect(url_for("useful_links_index", cat="__ALL__", error="Geen categorie meegegeven.") + "#manage")
        if not color.startswith("#") or len(color) != 7:
            return redirect(url_for("useful_links_index", cat="__ALL__", error="Kleur ongeldig.") + "#manage")

        db["categories"].setdefault(cat, {"color": DEFAULT_COLOR})
        if not isinstance(db["categories"][cat], dict):
            db["categories"][cat] = {"color": DEFAULT_COLOR}
        db["categories"][cat]["color"] = color
        save_db(db)
        return redirect(url_for("useful_links_index", cat=cat, msg="Kleur opgeslagen!") + "#manage")

    # ---- CATEGORY RENAME ----
    @app.route("/links/category/rename", methods=["POST"])
    def useful_links_category_rename():
        db = load_db()

        old_cat = _normalize_category_name(request.form.get("old_category") or "")
        new_cat = _normalize_category_name(request.form.get("new_category") or "")
        color = (request.form.get("color") or "").strip()
        move_links = bool(request.form.get("move_links"))

        if not old_cat:
            return redirect(url_for("useful_links_index", cat="__ALL__", error="Oude categorie ontbreekt.") + "#manage")
        if not new_cat:
            return redirect(url_for("useful_links_index", cat="__ALL__", error="Nieuwe categorie is verplicht.") + "#manage")
        if color and (not color.startswith("#") or len(color) != 7):
            return redirect(url_for("useful_links_index", cat="__ALL__", error="Kleur ongeldig.") + "#manage")

        db.setdefault("categories", {})
        if not isinstance(db["categories"], dict):
            db["categories"] = {}

        old_meta = db["categories"].get(old_cat, {"color": DEFAULT_COLOR})
        if not isinstance(old_meta, dict):
            old_meta = {"color": DEFAULT_COLOR}

        db["categories"].setdefault(new_cat, {})
        if not isinstance(db["categories"][new_cat], dict):
            db["categories"][new_cat] = {}
        db["categories"][new_cat].setdefault("color", old_meta.get("color") or DEFAULT_COLOR)

        if color:
            db["categories"][new_cat]["color"] = color

        if move_links:
            for r in db.get("links", []):
                if isinstance(r, dict) and (r.get("category") or "") == old_cat:
                    r["category"] = new_cat
                    r["updated"] = _now_iso()

        if (db.get("prefs", {}).get("default_category") or "").strip() == old_cat:
            db["prefs"]["default_category"] = new_cat

        if old_cat != new_cat:
            still_in_use = any(
                isinstance(r, dict) and (r.get("category") or "") == old_cat
                for r in db.get("links", [])
            )
            if not still_in_use:
                db["categories"].pop(old_cat, None)

        default_cat = db["prefs"]["default_category"]
        db["categories"].setdefault(default_cat, {"color": DEFAULT_COLOR})
        if not isinstance(db["categories"][default_cat], dict):
            db["categories"][default_cat] = {"color": DEFAULT_COLOR}
        db["categories"][default_cat].setdefault("color", DEFAULT_COLOR)

        save_db(db)
        return redirect(url_for("useful_links_index", cat="__ALL__", msg="Categorie hernoemd!") + "#manage")

    # ---- CATEGORY DELETE ----
    @app.route("/links/category/delete", methods=["POST"])
    def useful_links_category_delete():
        db = load_db()
        cat = _normalize_category_name(request.form.get("category") or "")
        if not cat:
            return redirect(url_for("useful_links_index", cat="__ALL__", error="Geen categorie meegegeven.") + "#manage")

        in_use = any(isinstance(r, dict) and (r.get("category") or "") == cat for r in db.get("links", []))
        if in_use:
            return redirect(url_for("useful_links_index", cat=cat, error="Categorie heeft nog links. Verplaats die eerst.") + "#manage")

        if (db.get("prefs", {}).get("default_category") or "").strip() == cat:
            return redirect(url_for("useful_links_index", cat="__ALL__", error="Dit is je default category. Kies eerst een andere default.") + "#manage")

        if isinstance(db.get("categories"), dict) and cat in db["categories"]:
            db["categories"].pop(cat, None)
            save_db(db)

        return redirect(url_for("useful_links_index", cat="__ALL__", msg="Categorie verwijderd!") + "#manage")
