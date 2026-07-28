"""Single source of truth for the application version.

In a dev checkout the version is derived live from git; in a frozen build it is read
from src/_version.py, which the build step writes from git and bundles into the exe.
"""
import datetime
import os
import subprocess
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FALLBACK_VERSION = "0.0.0"


def _git(*args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=_PROJECT_ROOT, capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def compute_from_git() -> dict | None:
    """Build the version info from the current git checkout, or None when git is unavailable."""
    build = _git("rev-list", "--count", "HEAD")
    short = _git("rev-parse", "--short=7", "HEAD")
    if build is None or short is None:
        return None
    dirty = bool(_git("status", "--porcelain"))
    today = datetime.date.today()
    version = f"{today.year}.{today.month}.{int(build)}"
    return {
        "version": version,
        "version_tuple": (today.year, today.month, int(build), 0),
        "git_hash": short,
        "build_date": today.isoformat(),
        "dirty": dirty,
        "version_full": f"{version} ({short}{'-dirty' if dirty else ''})",
    }


def _from_generated() -> dict | None:
    try:
        from src import _version as g  # generated at build time, git-ignored
    except Exception:
        return None
    return {
        "version": g.VERSION,
        "version_tuple": tuple(g.VERSION_TUPLE),
        "git_hash": g.GIT_HASH,
        "build_date": g.BUILD_DATE,
        "dirty": getattr(g, "DIRTY", False),
        "version_full": g.VERSION_FULL,
    }


def resolve() -> dict:
    """Frozen builds trust the baked file; dev checkouts prefer live git."""
    if getattr(sys, "frozen", False):
        info = _from_generated()
    else:
        info = compute_from_git() or _from_generated()
    return info or {
        "version": _FALLBACK_VERSION,
        "version_tuple": (0, 0, 0, 0),
        "git_hash": "unknown",
        "build_date": "",
        "dirty": False,
        "version_full": f"{_FALLBACK_VERSION}+local",
    }


def write_generated(info: dict, path: str) -> None:
    """Freeze the resolved version into a Python module the frozen app can import."""
    with open(path, "w", encoding="utf-8") as f:
        f.write('"""Generated at build time. Do not edit, do not commit."""\n')
        f.write(f'VERSION = {info["version"]!r}\n')
        f.write(f'VERSION_FULL = {info["version_full"]!r}\n')
        f.write(f'VERSION_TUPLE = {tuple(info["version_tuple"])!r}\n')
        f.write(f'GIT_HASH = {info["git_hash"]!r}\n')
        f.write(f'BUILD_DATE = {info["build_date"]!r}\n')
        f.write(f'DIRTY = {bool(info["dirty"])!r}\n')


_info = resolve()
VERSION = _info["version"]
VERSION_FULL = _info["version_full"]
VERSION_TUPLE = _info["version_tuple"]
GIT_HASH = _info["git_hash"]
BUILD_DATE = _info["build_date"]
