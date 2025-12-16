from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class NotifyError(RuntimeError):
    pass


@dataclass
class NotifyConfig:
    enabled: bool
    # Signal
    signal_cli_path: str
    signal_sender: str
    default_recipients: List[str]

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "NotifyConfig":
        d = d or {}
        return NotifyConfig(
            enabled=bool(d.get("enabled", False)),
            signal_cli_path=str(d.get("signal_cli_path") or "signal-cli"),
            signal_sender=str(d.get("signal_sender") or ""),
            default_recipients=[str(x).strip() for x in (d.get("default_recipients") or []) if str(x).strip()],
        )


def load_notify_config(base_dir: Path) -> NotifyConfig:
    """
    Reads config/notify.json. If absent: disabled.
    Example notify.json:
    {
      "enabled": true,
      "signal_cli_path": "C:/path/signal-cli.bat",
      "signal_sender": "+32....",
      "default_recipients": ["+32...."]
    }
    """
    path = base_dir / "config" / "notify.json"
    if not path.exists():
        return NotifyConfig.from_dict({"enabled": False})

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return NotifyConfig.from_dict({"enabled": False})
        return NotifyConfig.from_dict(data)
    except Exception:
        return NotifyConfig.from_dict({"enabled": False})


def _run(cmd: List[str], cwd: Path) -> Tuple[int, str]:
    """
    Runs a command and returns (exitcode, combined_output).
    """
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            errors="replace",
            shell=False,
        )
        out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        return int(p.returncode), out.strip()
    except Exception as e:
        return 999, str(e)


def send_signal(
    base_dir: Path,
    message: str,
    recipients: Optional[List[str]] = None,
    raise_on_fail: bool = False,
) -> bool:
    """
    Sends a Signal message via signal-cli.
    Returns True if sent, False otherwise.
    """
    cfg = load_notify_config(base_dir)
    if not cfg.enabled:
        return False

    msg = (message or "").strip()
    if not msg:
        if raise_on_fail:
            raise NotifyError("Signal message is empty")
        return False

    recips = recipients or cfg.default_recipients
    recips = [str(r).strip() for r in (recips or []) if str(r).strip()]
    if not recips:
        if raise_on_fail:
            raise NotifyError("No Signal recipients configured")
        return False

    if not cfg.signal_sender:
        if raise_on_fail:
            raise NotifyError("notify.json missing signal_sender")
        return False

    # signal-cli -u <sender> send -m "msg" <recip1> <recip2>
    cmd = [cfg.signal_cli_path, "-u", cfg.signal_sender, "send", "-m", msg] + recips
    code, out = _run(cmd, base_dir)

    ok = (code == 0)
    if not ok and raise_on_fail:
        raise NotifyError(f"Signal failed (exit={code}): {out}")
    return ok


def notify(
    base_dir: Path,
    message: str,
    recipients: Optional[List[str]] = None,
) -> bool:
    """
    Generic notify entrypoint (currently Signal).
    Later you can extend this with Telegram/Teams/etc without changing callers.
    """
    return send_signal(base_dir, message, recipients=recipients, raise_on_fail=False)
