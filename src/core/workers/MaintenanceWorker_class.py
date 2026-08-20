from PyQt6 import QtCore
from PyQt6.QtCore import QObject

from src.core.library import library_service
from src.core.log_system import print_e, print_traceback


class MaintenanceWorker(QObject):
    """Runs the library cleanup sweep on its own thread.

    The work itself lives in library_service, this only moves it off the GUI thread and
    turns the result into a signal.

    :signals: finished (object) - MaintenanceResult of the sweep,
              failed (str) - message when the sweep could not run
    """
    finished = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)

    def run(self) -> None:
        """Sweep the cover cache and the registry. Runs on the worker thread.

        :returns: None.
        """
        try:
            self.finished.emit(library_service.run_maintenance())
        except Exception as e:
            print_traceback()
            print_e("Library maintenance worker error:", e)
            self.failed.emit(str(e))