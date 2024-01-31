import os

import PyInstaller.__main__

from src.global_constants import APP_NAME, VERSION, GENRE_MODEL_PATH

BUILD_PATH: str = f"{APP_NAME} v{VERSION}"
TEMPLATE_SPEC_FILE: str = "main_template.spec"
SPEC_FILE: str = "main_generate.spec"


def parse_spec_file(path: str, out_path: str):
    out_f = open(out_path, 'w')
    in_f = open(path, 'r')

    for line in in_f:
        line = line.replace("$GENRE_MODEL_PATH", GENRE_MODEL_PATH)
        line = line.replace("$APP_NAME", APP_NAME)
        line = line.replace("$BUILD_PATH", BUILD_PATH)
        line = line.replace("$VERSION", VERSION)
        line = line.replace("$VENV_PATH", os.environ['VIRTUAL_ENV'].replace('\\', '/'))
        out_f.write(line)

    out_f.close()
    in_f.close()


if __name__ == '__main__':
    parse_spec_file(TEMPLATE_SPEC_FILE, SPEC_FILE)

    PyInstaller.__main__.run([
        SPEC_FILE,
        '-y'
    ])