"""Rebuilds the translation catalogs.

Scans the sources with pylupdate6 to refresh res/i18n/audionetlab_<lang>.ts, then
compiles every .ts into the .qm the application loads at runtime. Run it after
adding or changing any tr() string:

    venv\\Scripts\\python.exe tools/update_translations.py

New strings appear in the .ts as unfinished, translate them in Qt Linguist
(venv\\Scripts\\pyside6-linguist.exe res/i18n/audionetlab_ru.ts) and run the script again.
"""
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I18N_DIR = os.path.join(PROJECT_ROOT, "res", "i18n")
SOURCE_DIRS = ["src"]
SOURCE_FILES = ["main.py"]
LANGUAGES = ["ru"]  # Languages that need a catalog, the source language does not


def script_path(name: str) -> str:
    """Path of a console script inside the active interpreter environment.

    :param name: Script name without the extension.
    :returns: str - Full path to the executable.
    """
    scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    exe = os.path.join(scripts_dir, f"{name}.exe")
    return exe if os.path.exists(exe) else name


def collect_sources() -> list:
    """Collect every Python file that may contain translatable strings.

    :returns: list - Paths relative to the project root.
    """
    sources = list(SOURCE_FILES)
    for source_dir in SOURCE_DIRS:
        for root, _, files in os.walk(os.path.join(PROJECT_ROOT, source_dir)):
            if "__pycache__" in root:
                continue
            for file_name in files:
                if file_name.endswith(".py"):
                    sources.append(os.path.relpath(os.path.join(root, file_name), PROJECT_ROOT))
    return sorted(sources)


def main() -> int:
    """Update the .ts files and compile them into .qm.

    :returns: int - Process exit code.
    """
    os.makedirs(I18N_DIR, exist_ok=True)
    sources = collect_sources()
    print(f"Scanning {len(sources)} source files")

    for language in LANGUAGES:
        ts_path = os.path.join(I18N_DIR, f"audionetlab_{language}.ts")
        qm_path = os.path.join(I18N_DIR, f"audionetlab_{language}.qm")

        # pylupdate6 keeps the existing translations and only adds the new strings
        update = subprocess.run([script_path("pylupdate6"), *sources, "-ts", ts_path],
                                cwd=PROJECT_ROOT)
        if update.returncode != 0:
            print(f"pylupdate6 failed for '{language}'")
            return update.returncode

        release = subprocess.run([script_path("pyside6-lrelease"), ts_path, "-qm", qm_path],
                                 cwd=PROJECT_ROOT)
        if release.returncode != 0:
            print(f"lrelease failed for '{language}', install PySide6-Essentials")
            return release.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())