"""Files shipped inside the wheel: synthetic demo evidence and the AIX-side collectors.

In a wheel they live under ``aix_mcp/demo`` and ``aix_mcp/collectors`` (see ``pyproject.toml``).
In a source checkout they are read from ``tests/data`` and ``collectors/``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

_PKG = Path(__file__).resolve().parent
_REPO = _PKG.parent.parent

COLLECTOR_FILES = ("aix_storage_paths.ksh", "dispatch", "install_dispatch.ksh")


def _first_dir(*candidates: Path) -> Path:
    for c in candidates:
        if c.is_dir():
            return c
    raise FileNotFoundError("bundled files not found; reinstall aix-mcp")


def demo_dir() -> Path:
    """Synthetic evidence (host-01, vios-01). Not from any real system."""
    return _first_dir(_PKG / "demo", _REPO / "tests" / "data")


def collectors_dir() -> Path:
    return _first_dir(_PKG / "collectors", _REPO / "collectors")


def copy_collectors(dest: str | Path) -> list[Path]:
    """Copy the AIX-side scripts to ``dest`` (created if missing). Existing files are replaced."""
    src = collectors_dir()
    out = Path(dest)
    out.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in COLLECTOR_FILES:
        target = out / name
        shutil.copyfile(src / name, target)
        target.chmod(0o755)
        copied.append(target)
    return copied
