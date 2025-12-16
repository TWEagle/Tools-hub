# Tools-hub
tools-hub/
│
├─ app/
│   ├─ core.py          # Flask app, routes, lifecycle
│   ├─ home.py          # Homepage / grid
│   ├─ layout.py        # HTML + CSS helpers
│   ├─ theme.py         # kleuren, fonts, logo handling
│   ├─ branding.py      # laadt branding.json (DE sleutel)
│   ├─ notify.py        # Signal / notificaties
│   ├─ exports.py       # CSV / ZIP / downloads
│   ├─ health.py        # /health /metrics
│   └─ __init__.py
│
├─ tools/
│   ├─ cert_viewer.py
│   ├─ config_editor.py
│   ├─ useful_links.py
│   ├─ exe_builder.py
│   └─ ...
│
├─ launcher/
│   ├─ launcher.py      # brand-agnostic launcher
│   ├─ generate_cert.py # Python-only cert generator
│   └─ __init__.py
│
├─ config/
│   ├─ branding.json    # 👑 alles wat “naam” is
│   ├─ settings.json    # runtime settings
│   ├─ tools.json       # tool registry
│   └─ profiles/
│
├─ scripts/
│   ├─ start.ps1
│   ├─ stop.ps1
│   ├─ build_brand.ps1  # select tools + rebrand
│   └─ trust_cert.ps1
│
├─ assets/
│   ├─ logos/
│   ├─ icons/
│   └─ css/
│
├─ certs/
│   ├─ localhost.crt
│   └─ localhost.key
│
└─ run.py               # entrypoint (replaced ctools.py)
