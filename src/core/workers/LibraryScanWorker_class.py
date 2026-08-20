import threading
import time
from typing import List, Optional, Sequence

from PyQt6 import QtCore
from PyQt6.QtCore import QObject

from src.api.db.db_handler import create_session
from src.core.library.scanner import LibraryScanner, ScanStats
from src.core.log_system import print_e, print_traceback
from src.enums import ScanStage
from src.global_constants import SCAN_PROGRESS_INTERVAL_MS


class LibraryScanWorker(QObject):
    """Runs a library scan on its own thread.

    The scan itself lives in LibraryScanner, this only moves it off the GUI thread and
    turns its callbacks into signals. Progress is rate limited: a scan of a large
    library reports often enough to look alive, and flooding the event loop with
    signals would slow down the very interface the thread exists to keep responsive.

    :signals: progress (str, int, int) - stage, items done, items in total,
              finished (object) - ScanStats of the finished scan,
              failed (str) - message when the scan could not run
    """
    progress = QtCore.pyqtSignal(str, int, int)
    finished = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        """Create the worker, paths are assigned before run().

        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.paths: List[str] = []
        self.cancel_event = threading.Event()
        self._last_emit: float = 0.0
        self._last_stage: Optional[ScanStage] = None

    def set_paths(self, paths: Sequence[str]) -> None:
        """Set what the next run imports and clear a previous cancel.

        :param paths: Files and folders to import.
        :returns: None.
        """
        self.paths = list(paths)
        self.cancel_event.clear()
        self._last_emit = 0.0
        self._last_stage = None

    def cancel(self) -> None:
        """Ask the running scan to stop after the current chunk.

        Safe to call from the GUI thread, the scan only reads the event.

        :returns: None.
        """
        self.cancel_event.set()

    def run(self) -> None:
        """Scan the assigned paths. Runs on the worker thread.

        :returns: None.
        """
        session = None
        try:
            session = create_session()  # A session belongs to one thread
            scanner = LibraryScanner(session=session,
                                     progress_callback=self._on_progress,
                                     cancel_event=self.cancel_event)
            stats: ScanStats = scanner.scan(self.paths)
            self.finished.emit(stats)
        except Exception as e:
            print_traceback()
            print_e("Library scan worker error:", e)
            self.failed.emit(str(e))
        finally:
            if session is not None:
                session.close()

    def _on_progress(self, stage: ScanStage, done: int, total: int) -> None:
        """Forward the scanner progress, dropping the updates that come too fast.

        A stage change and the last update of a stage always go through, so the bar
        never stops one step short of the end.

        :param stage: Current stage.
        :param done: Items handled.
        :param total: Items in total, 0 while it is still unknown.
        :returns: None.
        """
        now = time.monotonic()
        is_final = total > 0 and done >= total
        if (stage is self._last_stage and not is_final
                and (now - self._last_emit) * 1000 < SCAN_PROGRESS_INTERVAL_MS):
            return
        self._last_emit = now
        self._last_stage = stage
        self.progress.emit(stage.value, done, total)
