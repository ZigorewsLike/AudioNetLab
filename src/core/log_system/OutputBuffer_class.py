import sys
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from src.global_constants import LOG_IN_FILE, LOG_IN_SIGNAL
from src.core.log_system import ConsoleColors


class OutputBuffer(QObject):
    widget_print = pyqtSignal(str)

    def __init__(self):
        super(OutputBuffer, self).__init__()
        self.console = sys.stdout
        if LOG_IN_FILE:
            self.log_in_file(f"\n  == RUN | {datetime.now().strftime('%Y.%m.%d %H:%M:%S')} == \n")

    def write(self, text: str):
        if LOG_IN_FILE:
            self.log_in_file(text.replace(ConsoleColors.DEBUG, '').replace(ConsoleColors.SIMPLE, ''))

        self.console.write(text)
        self.console.flush()

        if LOG_IN_SIGNAL:
            self.widget_print.emit(text)

    @staticmethod
    def log_in_file(text: str) -> None:
        f = open(f"logs/{datetime.now().strftime('%Y-%m-%d')}_log.txt", "a")
        f.write(text)
        f.close()

    def flush(self):
        self.console.flush()

    def reset(self):
        sys.stdout = self.console
