import subprocess
import sys

from src.core.log_system import print_e


def reveal_in_file_manager(path: str) -> None:
    """Open the system file manager with a file selected.

    :param path: Path to the file to reveal.
    :returns: None.
    """
    if not path:
        return
    try:
        if sys.platform == "win32":
            native_path = path.replace("/", "\\")  # Explorer does not follow forward slashes
            subprocess.call(f'explorer /select,"{native_path}"')
        else:
            subprocess.call(["open", "-R", path])
    except Exception as e:
        print_e("Reveal in file manager failed", e)