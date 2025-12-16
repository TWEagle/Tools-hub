#!/usr/bin/env python3
"""Brand-agnostic launcher for Tools Hub (Windows-friendly).

- Creates venv if missing
- Installs deps from requirements.txt (once; stamp file)
- Picks a free port
- Starts run.py (and restarts if it crashes)
- Logs stdout/stderr to logs/app.log
- Optional tray icon (pystray) if available
- Optional HTTPS (self-signed localhost cert via cryptography; no OpenSSL)
"""

from __future__ import annotations

import os
import sys
import time
import socket
import threading
import subprocess
from pathlib import Path
from datetime import datetime

try:
    from urllib.request import urlopen
    from urllib.error import URLError
except Exception:
    urlopen = None
    URLError = Exception

ROOT_DIR = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT_DIR / "venv"
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LAUNCHER_LOG = LOG_DIR / "launcher.log"
APP_LOG = LOG_DIR / "app.log"

REQ_FILE = ROOT_DIR / "requirements.txt"
DEPS_STAMP = VENV_DIR / ".deps_installed"

CERT_DIR = ROOT_DIR / "certs"

DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_URL_HOST = "localhost"
DEFAULT_PORT = 5000
PORT_SCAN_MAX = 80

HEALTH_PATH = "/health"
HEALTH_TIMEOUT_SEC = 25
HEALTH_POLL_INTERVAL = 0.5

TRAY_PKGS = ["pillow", "pystray"]
REQUIRED_FALLBACK = ["flask"] + TRAY_PKGS

STOP_EVENT = threading.Event()
STATE = {"url": None, "port": None, "proc": None}


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        prev = LAUNCHER_LOG.read_text(encoding="utf-8", errors="ignore") if LAUNCHER_LOG.exists() else ""
        LAUNCHER_LOG.write_text(prev + line + "\n", encoding="utf-8")
    except Exception:
        pass


def popup_info(title: str, message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(title, message)
        root.destroy()
    except Exception:
        log(f"[POPUP-FAIL] {title}: {message}")


def _read_json(path: Path) -> dict:
    try:
        import json
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def load_settings() -> dict:
    return _read_json(ROOT_DIR / "config" / "settings.json")


def load_branding() -> dict:
    return _read_json(ROOT_DIR / "config" / "branding.json")


def ensure_venv() -> Path:
    py_exe = VENV_DIR / "Scripts" / "python.exe"
    if py_exe.exists():
        return py_exe
    log("venv ontbreekt -> aanmaken...")
    import venv
    venv.EnvBuilder(with_pip=True).create(str(VENV_DIR))
    if not py_exe.exists():
        raise RuntimeError("venv aangemaakt maar python.exe niet gevonden in venv\\Scripts")
    log("venv aangemaakt.")
    return py_exe


def run_pip(venv_python: Path, args: list[str]) -> int:
    cmd = [str(venv_python), "-m", "pip"] + args
    log("PIP: " + " ".join(args))
    return subprocess.call(cmd, cwd=str(ROOT_DIR))


def ensure_packages(venv_python: Path) -> None:
    if DEPS_STAMP.exists():
        return

    run_pip(venv_python, ["install", "--upgrade", "pip", "setuptools", "wheel"])

    if REQ_FILE.exists():
        log("requirements.txt gevonden -> installeren...")
        code = run_pip(venv_python, ["install", "-r", str(REQ_FILE)])
        # always ensure tray deps (some requirements files are trimmed)
        run_pip(venv_python, ["install", "--upgrade"] + TRAY_PKGS)
        if code != 0:
            log("⚠ requirements install faalde; fallback minimum packages...")
            run_pip(venv_python, ["install"] + REQUIRED_FALLBACK)
    else:
        log("requirements.txt niet gevonden -> minimum packages installeren...")
        run_pip(venv_python, ["install"] + REQUIRED_FALLBACK)

    try:
        DEPS_STAMP.write_text("ok", encoding="utf-8")
    except Exception:
        pass


def is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def pick_free_port(host: str, preferred: int) -> int:
    for p in range(preferred, preferred + PORT_SCAN_MAX):
        if is_port_free(host, p):
            return p
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return int(s.getsockname()[1])


def wait_for_health(url_base: str, timeout_sec: float) -> bool:
    if urlopen is None:
        time.sleep(2)
        return True

    health_url = url_base.rstrip("/") + HEALTH_PATH
    deadline = time.time() + timeout_sec

    while time.time() < deadline and not STOP_EVENT.is_set():
        try:
            with urlopen(health_url, timeout=2) as resp:
                if getattr(resp, "status", 200) == 200:
                    return True
        except URLError:
            pass
        except Exception:
            pass
        time.sleep(HEALTH_POLL_INTERVAL)
    return False


def open_edge(url: str) -> None:
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", f"microsoft-edge:{url}"],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except Exception as e:
        log(f"[WARN] Kon Edge niet openen via protocol: {e}")
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass


def ensure_localhost_certs(venv_python: Path, want_https: bool, brand: dict) -> tuple[Path, Path] | tuple[None, None]:
    if not want_https:
        return None, None

    from .generate_cert import generate_localhost_cert

    cert_cfg = brand.get("cert", {}) if isinstance(brand, dict) else {}
    cn = str(cert_cfg.get("common_name") or "localhost")
    crt_name = str(cert_cfg.get("cert_filename") or "localhost.crt")
    key_name = str(cert_cfg.get("key_filename") or "localhost.key")

    crt = CERT_DIR / crt_name
    key = CERT_DIR / key_name

    # validate existing PEM quickly (avoid SSL PEM lib crash)
    if crt.exists() and key.exists():
        try:
            crt_txt = crt.read_text(encoding="utf-8", errors="ignore")
            key_txt = key.read_text(encoding="utf-8", errors="ignore")
            if "BEGIN CERTIFICATE" in crt_txt and "BEGIN" in key_txt and "PRIVATE KEY" in key_txt:
                return crt, key
        except Exception:
            pass
        try:
            crt.unlink(missing_ok=True)
            key.unlink(missing_ok=True)
        except Exception:
            pass

    log("HTTPS requested -> generating self-signed localhost cert (Python-only)...")
    try:
        generate_localhost_cert(cert_path=crt, key_path=key, common_name=cn)
        return crt, key
    except Exception as e:
        log(f"[WARN] Cert generation failed: {e} -> trying cryptography upgrade")
        run_pip(venv_python, ["install", "--upgrade", "cryptography"])
        try:
            generate_localhost_cert(cert_path=crt, key_path=key, common_name=cn)
            return crt, key
        except Exception as e2:
            log(f"[ERROR] Cert generation retry failed: {e2}")
            return None, None


def start_app(venv_python: Path, bind_host: str, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["HUB_HOST"] = bind_host
    env["HUB_PORT"] = str(port)
    env["HUB_LAUNCHED"] = "1"
    env.setdefault("PYTHONUTF8", "1")

    try:
        if APP_LOG.exists() and APP_LOG.stat().st_size > 5_000_000:
            APP_LOG.rename(LOG_DIR / f"app_{int(time.time())}.log")
    except Exception:
        pass

    f = open(APP_LOG, "a", encoding="utf-8", errors="ignore")
    cmd = [str(venv_python), str(ROOT_DIR / "run.py")]

    log(f"Start app: {' '.join(cmd)} (bind_host={bind_host}, port={port})")
    return subprocess.Popen(
        cmd,
        cwd=str(ROOT_DIR),
        env=env,
        stdout=f,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def kill_process(proc: subprocess.Popen) -> None:
    try:
        if proc.poll() is None:
            proc.terminate()
            time.sleep(1.5)
        if proc.poll() is None:
            proc.kill()
    except Exception:
        pass


def tray_thread(brand: dict) -> None:
    try:
        import pystray
        from pystray import MenuItem as Item
        from PIL import Image
    except Exception as e:
        log(f"Tray deps niet beschikbaar (pystray/pillow): {e}")
        return

    title = str(brand.get("tray_title") or brand.get("app_name") or "Tools Hub")
    logo_rel = None
    assets = brand.get("assets", {}) if isinstance(brand, dict) else {}
    if isinstance(assets, dict):
        logo_rel = assets.get("logo_tray") or assets.get("logo_web")

    logo = ROOT_DIR / str(logo_rel) if logo_rel else None
    if logo and logo.exists():
        try:
            image = Image.open(logo).convert("RGBA")
        except Exception:
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    else:
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))

    def _get_url() -> str:
        return STATE.get("url") or "(not ready)"

    def on_open(icon, item):
        url = STATE.get("url")
        if url:
            open_edge(url)

    def on_copy(icon, item):
        url = STATE.get("url") or ""
        if not url:
            return
        try:
            import tkinter as tk
            r = tk.Tk()
            r.withdraw()
            r.clipboard_clear()
            r.clipboard_append(url)
            r.update()
            r.destroy()
        except Exception:
            pass

    def on_restart(icon, item):
        proc = STATE.get("proc")
        if proc:
            kill_process(proc)

    def on_quit(icon, item):
        STOP_EVENT.set()
        proc = STATE.get("proc")
        if proc:
            kill_process(proc)
        try:
            icon.stop()
        except Exception:
            pass

    menu = pystray.Menu(
        Item("Open", on_open),
        Item("Copy URL", on_copy),
        Item("Restart", on_restart),
        Item("Quit", on_quit),
        Item(lambda item: f"URL: {_get_url()}", None, enabled=False),
    )

    icon = pystray.Icon("ToolsHub", image, title, menu)
    icon.run()


def main() -> int:
    settings = load_settings()
    brand = load_branding()

    popup_title = str(brand.get("popup_title") or brand.get("app_name") or "Tools Hub")

    log("=== Launcher start ===")

    try:
        venv_python = ensure_venv()
    except Exception as e:
        popup_info(popup_title, f"Fout bij venv aanmaken:\n{e}")
        return 1

    try:
        ensure_packages(venv_python)
    except Exception as e:
        popup_info(popup_title, f"Fout bij packages installeren:\n{e}\n\nZie logs/launcher.log")
        return 1

    https_cfg = settings.get("https", {}) if isinstance(settings, dict) else {}
    want_https = bool(https_cfg.get("enabled", False))

    # Ensure certs if HTTPS requested
    crt, key = ensure_localhost_certs(venv_python, want_https, brand)
    if want_https and (not crt or not key):
        log("[WARN] HTTPS enabled but certs not available -> continuing; app will fallback to HTTP.")

    bind_host = os.environ.get("HUB_BIND_HOST", DEFAULT_BIND_HOST).strip() or DEFAULT_BIND_HOST
    preferred = int(os.environ.get("HUB_PORT", str(DEFAULT_PORT)))
    port = pick_free_port(bind_host, preferred)

    url_host = os.environ.get("HUB_URL_HOST", str(https_cfg.get("url_host", DEFAULT_URL_HOST))).strip() or DEFAULT_URL_HOST
    scheme = "https" if want_https else "http"
    url_base = f"{scheme}://{url_host}:{port}/"

    STATE["port"] = port
    STATE["url"] = url_base

    threading.Thread(target=tray_thread, args=(brand,), daemon=True).start()

    backoff = 1.0
    first_start = True

    while not STOP_EVENT.is_set():
        proc = start_app(venv_python, bind_host, port)
        STATE["proc"] = proc

        if first_start:
            first_start = False

            ok = wait_for_health(url_base, HEALTH_TIMEOUT_SEC)

            # Fallback: HTTPS health sometimes fails due to privacy warning / untrusted cert
            if not ok and url_base.startswith("https://"):
                fallback = "http://" + url_base[len("https://"):]
                log(f"[INFO] HTTPS health failed -> trying HTTP fallback: {fallback}")
                ok = wait_for_health(fallback, 8)
                if ok:
                    url_base = fallback
                    STATE["url"] = url_base

            if ok:
                popup_info(popup_title, f"App is klaar op:\n{url_base}\n\n(ook in de tray te vinden)")
                open_edge(url_base)
            else:
                popup_info(
                    popup_title,
                    "App startte, maar /health werd niet OK binnen de timeout.\n\n"
                    f"Probeer manueel:\n{url_base}\n\n"
                    "Bekijk logs/app.log voor details."
                )

        while proc.poll() is None and not STOP_EVENT.is_set():
            time.sleep(0.5)

        if STOP_EVENT.is_set():
            kill_process(proc)
            break

        code = proc.poll()
        log(f"⚠ App gestopt (exit code={code}). Auto-restart in {backoff:.1f}s ...")
        time.sleep(backoff)
        backoff = min(backoff * 1.5, 15.0)

    log("=== Launcher stop ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        STOP_EVENT.set()
        sys.exit(0)
