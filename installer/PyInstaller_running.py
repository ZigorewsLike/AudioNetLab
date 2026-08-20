import os
import shutil

import PyInstaller.__main__

from src.global_constants import APP_NAME, APP_AUTHOR, APP_COPYRIGHT, GENRE_MODEL_PATH
from src.version import compute_from_git, resolve, write_generated

TEMPLATE_SPEC_FILE: str = "main_template.spec"
SPEC_FILE: str = "main_generate.spec"
CONTENTS_DIRECTORY = "bin"
GENERATED_VERSION_FILE = "src/_version.py"


def parse_spec_file(path: str, out_path: str, subs: dict):
    out_f = open(out_path, 'w', encoding='utf-8')
    in_f = open(path, 'r', encoding='utf-8')

    for line in in_f:
        for key, value in subs.items():
            line = line.replace(key, value)
        out_f.write(line)

    out_f.close()
    in_f.close()


if __name__ == '__main__':
    info = compute_from_git() or resolve()

    if info["dirty"]:
        print(f"[build] WARNING: working tree is dirty — {info['version_full']} is not reproducible.")
    print(f"[build] Version {info['version_full']}  hash={info['git_hash']}  date={info['build_date']}")

    # Freeze the git-derived version so the frozen exe reports the exact build.
    write_generated(info, GENERATED_VERSION_FILE)

    BUILD_PATH = f"{APP_NAME} v{info['version']}"
    substitutions = {
        "$GENRE_MODEL_PATH": GENRE_MODEL_PATH,
        "$APP_NAME": APP_NAME,
        "$APP_AUTHOR": APP_AUTHOR,
        "$COPYRIGHT": APP_COPYRIGHT,
        "$BUILD_PATH": BUILD_PATH,
        "$VERSION_FULL": info["version_full"],
        "$VERSION_TUPLE": ", ".join(str(n) for n in info["version_tuple"]),
        "$VERSION": info["version"],
        "$GIT_HASH": info["git_hash"],
        "$VENV_PATH": os.environ['VIRTUAL_ENV'].replace('\\', '/'),
        "$CONTENT_DIR": CONTENTS_DIRECTORY,
    }
    parse_spec_file(TEMPLATE_SPEC_FILE, SPEC_FILE, substitutions)

    PyInstaller.__main__.run([
        SPEC_FILE,
        '-y'
    ])

    print("## Directory preparing")
    build_path = os.path.abspath(os.path.join('dist', BUILD_PATH))
    dir_list = ["res", "models"]
    for _dir_name in dir_list:
        folder_path = os.path.join(build_path, CONTENTS_DIRECTORY, _dir_name)
        save_path = os.path.join(build_path, _dir_name)

        print(f"{_dir_name} > {save_path}")
        shutil.move(folder_path, save_path)
    print("## Complete")
