from typing import TYPE_CHECKING

from PyQt6 import QtCore
from PyQt6.QtCore import QObject, QCoreApplication

from src.core.log_system import print_e, print_traceback

if TYPE_CHECKING:
    from src.forms import MainForm


class OpenFileWorker(QObject):
    """Worker that decodes an audio file outside the UI thread.

    :signals: finished (str) - path of the opened file, empty string on failure,
              preloader_signal (str) - progress text for the preloader
    """
    finished = QtCore.pyqtSignal(str)
    mf = None  # MainForm
    preloader_signal = QtCore.pyqtSignal(str)
    file_path: str

    def __init__(self):
        """Create the worker, mf and file_path are assigned before run().

        :returns: None.
        """
        super().__init__()

    def run(self) -> None:
        """Decode the file into the player and report the result.

        :returns: None.
        """
        try:
            # Not a QWidget, so the context has to be named explicitly
            self.preloader_signal.emit(QCoreApplication.translate("OpenFileWorker", "Opening the file, decoding audio"))
            self.mf.audio_player.open_file(self.file_path)

            self.preloader_signal.emit(QCoreApplication.translate("OpenFileWorker", "Opening the file, almost done"))
            self.finished.emit(self.file_path)
        except Exception as e:
            print_traceback()
            print_e("Worker error:", e)
            self.finished.emit("")  # Empty path tells the form that opening failed