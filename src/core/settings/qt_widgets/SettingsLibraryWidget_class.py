from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSlot, QEvent, QThread
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from src.core.library.library_service import MaintenanceResult
from src.core.settings.qt_widgets.SettingsSection_class import SettingsSection
from src.core.workers import MaintenanceWorker

if TYPE_CHECKING:
    from src.forms import MainForm


class SettingsLibraryWidget(QWidget):
    """Settings page for looking after the library data on disk.

    Deleting a track drops what belongs to it right away, so the sweep here is for what
    slipped past that: covers of albums removed by an older version, registry folders of
    tracks that are long gone, and cached sizes left over from a change to the cache.
    """

    def __init__(self, mf, *args, **kwargs):
        """Build the page.

        :param mf: Main form reference.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf

        self._thread = QThread(self)
        self._worker = MaintenanceWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self.on_finished)
        self._worker.failed.connect(self.on_failed)

        root = QVBoxLayout(self)

        self.cleanup_section = SettingsSection(self)
        self.cleanup_label = QLabel("")
        self.cleanup_label.setWordWrap(True)
        self.cleanup_button = QPushButton("")
        self.cleanup_button.clicked.connect(self.on_cleanup_clicked)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.cleanup_section.add_full_row(self.cleanup_label)
        self.cleanup_section.add_full_row(self.cleanup_button)
        self.cleanup_section.add_full_row(self.result_label)

        root.addWidget(self.cleanup_section)
        root.addStretch(1)

        self.retranslate_ui()

    @pyqtSlot()
    def on_cleanup_clicked(self) -> None:
        """Start the sweep on its own thread.

        :returns: None.
        """
        if self._thread.isRunning():
            return
        if self.mf.scan_thread.isRunning():
            self.result_label.setText(self.tr("A scan is running, try again once it is done"))
            return
        self.cleanup_button.setEnabled(False)
        self.result_label.setText(self.tr("Cleaning up…"))
        self._thread.start()

    @pyqtSlot(object)
    def on_finished(self, result: MaintenanceResult) -> None:
        """Report what the sweep removed and refresh the library views.

        :param result: What the sweep threw away.
        :returns: None.
        """
        self._thread.quit()
        self.cleanup_button.setEnabled(True)
        if result.bytes_freed or result.albums or result.artists:
            self.result_label.setText(self.tr("Removed {0} covers and {1} track folders, {2} freed")
                                      .format(result.cover_files, result.registry_folders,
                                              self._format_size(result.bytes_freed)))
        else:
            self.result_label.setText(self.tr("Nothing to clean up"))
        if result.albums or result.artists:
            self.mf.library_widget.reload()

    @pyqtSlot(str)
    def on_failed(self, message: str) -> None:
        """Report a sweep that could not run.

        :param message: Error text.
        :returns: None.
        """
        self._thread.quit()
        self.cleanup_button.setEnabled(True)
        self.result_label.setText(self.tr("Cleanup failed: {0}").format(message))

    def shutdown(self) -> None:
        """Wait for a running sweep, called when the window closes.

        :returns: None.
        """
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(5000)

    @staticmethod
    def _format_size(size: int) -> str:
        """Format a number of bytes for the result line.

        :param size: Size in bytes.
        :returns: str - Size with a unit.
        """
        if size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / 1024:.0f} KB"

    def changeEvent(self, event: QEvent) -> None:
        """Reapply the texts when the application language changes.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self) -> None:
        """Apply the current translation to the texts of this page.

        :returns: None.
        """
        self.cleanup_section.set_title(self.tr("Cached data"))
        self.cleanup_label.setText(
            self.tr("Covers and per-track data of albums that are no longer in the library "
                    "can be left over on disk. Cleaning up removes them; the library itself "
                    "and the audio files are not affected."))
        self.cleanup_button.setText(self.tr("Clean up now"))