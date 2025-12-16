from __future__ import annotations
from pathlib import Path


class Paths:
    """
    Centrale paden voor de hele hub.
    Base_dir = root van de repo (waar run.py staat).
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()

        self.app_dir = self.base_dir / "app"
        self.tools_dir = self.base_dir / "tools"
        self.config_dir = self.base_dir / "config"
        self.assets_dir = self.base_dir / "assets"
        self.certs_dir = self.base_dir / "certs"
        self.logs_dir = self.base_dir / "logs"

        # Docs/help
        self.help_dir = self.base_dir / "help"          # alle md’s hier
        self.default_about = self.base_dir / "ABOUT.md" # fallback als je dat wil behouden

    def ensure_dirs(self) -> None:
        for d in (self.logs_dir, self.certs_dir):
            d.mkdir(parents=True, exist_ok=True)
