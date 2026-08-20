import os
import sys
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from src.global_constants import LOG_IN_FILE, LOG_IN_SIGNAL, LOG_DIR
from src.core.log_system import ConsoleColors


class OutputBuffer(QObject):
    """stdout replacement that mirrors the console output into a file and a Qt signal.

    :signals: widget_print (str) - printed text when LOG_IN_SIGNAL is on
    """
    widget_print = pyqtSignal(str)

    def __init__(self):
        super(OutputBuffer, self).__init__()
        self.console = sys.stdout
        if LOG_IN_FILE:
            os.makedirs(LOG_DIR, exist_ok=True)
            self.log_in_file(f"\n  == RUN | {datetime.now().strftime('%Y.%m.%d %H:%M:%S')} == \n")

    def write(self, text: str):
        if LOG_IN_FILE:
            self.log_in_file(text.replace(ConsoleColors.DEBUG, '').replace(ConsoleColors.SIMPLE, ''))

        # A windowed (console=False) build has no stdout, PyInstaller sets it to None.
        if self.console is not None:
            self.console.write(text)
            self.console.flush()

        if LOG_IN_SIGNAL:
            self.widget_print.emit(text)

    @staticmethod
    def log_in_file(text: str) -> None:
        f = open(f"{LOG_DIR}/{datetime.now().strftime('%Y-%m-%d')}_log.txt", "a")
        f.write(text)
        f.close()

    def flush(self):
        if self.console is not None:
            self.console.flush()

    def reset(self):
        sys.stdout = self.console
