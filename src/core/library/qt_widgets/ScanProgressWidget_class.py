from typing import Optional

from PyQt6 import QtCore
from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QWidget

from src.enums import ScanStage
from src.global_styles import AppColorSchemes


class ScanProgressWidget(QWidget):
    """Slim strip reporting a running library scan.

    Deliberately not a modal overlay: importing a folder can take minutes and the
    player has to stay usable while it runs, so this only occupies a strip at the
    bottom of the window and disappears when the scan is over.

    :signals: cancelRequested () - the cancel button was pressed,
              visibilityChanged () - the strip appeared or disappeared and the window
              around it has to give back the space
    """
    cancelRequested = QtCore.pyqtSignal()
    visibilityChanged = QtCore.pyqtSignal()

    # How long the finished summary stays on screen before the strip hides itself
    SUMMARY_TIMEOUT_MS = 4000

    def __init__(self, *args, **kwargs):
        """Build the strip, hidden until a scan starts.

        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.setFixedHeight(34)
        self.setVisible(False)

        self._stage: ScanStage = ScanStage.WALK
        self._summary: Optional[str] = None

        self.setStyleSheet(f"""
        QWidget {{
            background-color: {AppColorSchemes.FILE_LIST_ITEM_BODY};
        }}
        QLabel {{
            color: black;
            background-color: transparent;
        }}
        QProgressBar {{
            background-color: {AppColorSchemes.SCROLLBAR_BACKGROUND};
            border: 0px;
            border-radius: 4px;
            text-align: center;
            color: black;
        }}
        QProgressBar::chunk {{
            background-color: #60FF88;
            border-radius: 4px;
        }}
        QPushButton {{
            background-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
            border: 0px;
            border-radius: 4px;
            color: black;
            padding: 4px 12px;
        }}
        QPushButton:hover {{
            background-color: {AppColorSchemes.BUTTON_HOVER};
        }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)

        font = QFont("Arima")
        font.setPointSize(9)

        self.label_stage = QLabel("", self)
        self.label_stage.setFont(font)
        self.label_stage.setMinimumWidth(180)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setFont(font)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setRange(0, 0)  # Busy indicator until a total is known

        self.button_cancel = QPushButton("", self)
        self.button_cancel.setFont(font)
        self.button_cancel.clicked.connect(self._on_cancel_clicked)

        layout.addWidget(self.label_stage)
        layout.addWidget(self.progress_bar, 1)
        layout.addWidget(self.button_cancel)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(lambda: self.setVisible(False))

        self.retranslate_ui()

    def showEvent(self, event) -> None:
        """Tell the window the strip now takes space.

        :param event: Qt show event.
        :returns: None.
        """
        super().showEvent(event)
        self.visibilityChanged.emit()

    def hideEvent(self, event) -> None:
        """Tell the window the strip gave its space back.

        :param event: Qt hide event.
        :returns: None.
        """
        super().hideEvent(event)
        self.visibilityChanged.emit()

    def changeEvent(self, event: QEvent) -> None:
        """Reapply the texts when the application language changes.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self) -> None:
        """Apply the current translation to the caption and the button.

        :returns: None.
        """
        self.button_cancel.setText(self.tr("Cancel"))
        if self._summary is None:
            self.label_stage.setText(self._stage_text(self._stage))

    def _stage_text(self, stage: ScanStage) -> str:
        """Caption of one scan stage.

        :param stage: Stage to describe.
        :returns: str - Translated caption.
        """
        if stage is ScanStage.WALK:
            return self.tr("Looking for audio files")
        if stage is ScanStage.READ:
            return self.tr("Reading tags and covers")
        if stage is ScanStage.FINALIZE:
            return self.tr("Updating the library")
        return self.tr("Done")

    @QtCore.pyqtSlot()
    def start(self) -> None:
        """Show the strip at the beginning of a scan.

        :returns: None.
        """
        self._hide_timer.stop()
        self._summary = None
        self._stage = ScanStage.WALK
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("")
        self.label_stage.setText(self._stage_text(self._stage))
        self.button_cancel.setEnabled(True)
        self.setVisible(True)

    @QtCore.pyqtSlot(str, int, int)
    def set_progress(self, stage: str, done: int, total: int) -> None:
        """Show the progress reported by the scan worker.

        :param stage: Value of the current ScanStage.
        :param done: Items handled.
        :param total: Items in total, 0 while it is still unknown.
        :returns: None.
        """
        if self._summary is not None:
            return  # A late update must not overwrite the finished summary
        try:
            self._stage = ScanStage(stage)
        except ValueError:
            return
        self.label_stage.setText(self._stage_text(self._stage))

        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(done)
            self.progress_bar.setFormat(f"{done} / {total}")
        else:
            # Nothing to divide by yet, keep the bar busy and show the running count
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat(str(done) if done else "")

    @QtCore.pyqtSlot(str)
    def finish(self, summary: str) -> None:
        """Show what the scan did, then hide the strip.

        :param summary: Already translated summary line.
        :returns: None.
        """
        self._summary = summary
        self.label_stage.setText(summary)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.progress_bar.setFormat("")
        self.button_cancel.setEnabled(False)
        self.setVisible(True)
        self._hide_timer.start(self.SUMMARY_TIMEOUT_MS)

    def _on_cancel_clicked(self) -> None:
        """Ask for the scan to stop and disable the button.

        :returns: None.
        """
        self.button_cancel.setEnabled(False)
        self.label_stage.setText(self.tr("Stopping"))
        self.cancelRequested.emit()
