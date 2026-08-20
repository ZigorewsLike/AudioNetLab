from typing import Optional, TYPE_CHECKING

from PyQt6 import QtCore
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPainter
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
                             QWidget)

from src.api.db.db_handler import create_session
from src.api.db import library_repo
from src.core.library.AlbumTracksModel_class import format_duration
from src.enums import PlayerState
from src.function_lib.qt_utils import status_icon_pixmap
from src.global_styles import AppColorSchemes, DEFAULT_SCROLLBAR_STYLE

if TYPE_CHECKING:
    from src.forms import MainForm

# Edge length of the play or pause marker drawn in the left inset of a queue row
_STATUS_ICON_SIZE = 14


class QueueRow(QFrame):
    """One row of the queue: a marker or position, the title, artist and length.

    :signals: clicked (int) - track id of the row,
              removeRequested (int) - queue position to remove
    """
    clicked = QtCore.pyqtSignal(int)
    removeRequested = QtCore.pyqtSignal(int)

    def __init__(self, position: int, track_id: int, title: str, artist: Optional[str],
                 duration: Optional[float], is_current: bool, paused: bool, removable: bool,
                 *args, **kwargs):
        """Build a row.

        :param position: Index in the queue, used when removing.
        :param track_id: Track id.
        :param title: Track title.
        :param artist: Artist name.
        :param duration: Length in seconds.
        :param is_current: Whether this is the track being played.
        :param paused: Whether the current track is paused.
        :param removable: Whether a remove button is shown.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self._position = position
        self._track_id = track_id
        self._is_current = is_current
        self._paused = paused
        self.setFixedHeight(46)
        self.setObjectName("QueueRow")
        self.setStyleSheet("""
        QFrame#QueueRow { background-color: transparent; border-radius: 6px; }
        QFrame#QueueRow:hover { background-color: rgba(0, 0, 0, 26); }
        QLabel { background-color: transparent; }
        QPushButton#Remove {
            background-color: transparent; border: 0px; color: #777777; font-size: 14px;
        }
        QPushButton#Remove:hover { color: #b03030; }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(34, 4, 8, 4)  # Left inset leaves room for the marker
        layout.setSpacing(8)

        text = QVBoxLayout()
        text.setSpacing(0)
        self.title_label = QLabel(title, self)
        title_font = QFont("Arima")
        title_font.setPointSize(10)
        title_font.setBold(is_current)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet(f"color: {'#2f8f43' if is_current else '#141414'};")
        self.artist_label = QLabel(artist or "", self)
        artist_font = QFont("Arima")
        artist_font.setPointSize(8)
        self.artist_label.setFont(artist_font)
        self.artist_label.setStyleSheet("color: #777777;")
        text.addWidget(self.title_label)
        text.addWidget(self.artist_label)

        self.duration_label = QLabel(format_duration(duration), self)
        duration_font = QFont("Arima")
        duration_font.setPointSize(8)
        self.duration_label.setFont(duration_font)
        self.duration_label.setStyleSheet("color: #6a6a6a;")

        layout.addLayout(text, 1)
        layout.addWidget(self.duration_label)

        if removable:
            self.remove_button = QPushButton("✕", self)
            self.remove_button.setObjectName("Remove")
            self.remove_button.setFixedSize(22, 22)
            self.remove_button.clicked.connect(lambda: self.removeRequested.emit(self._position))
            layout.addWidget(self.remove_button)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Play this row's track on a click.

        :param event: Qt mouse event.
        :returns: None.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._track_id)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        """Draw the play or pause marker icon on the current row.

        :param event: Qt paint event.
        :returns: None.
        """
        super().paintEvent(event)
        if not self._is_current:
            return
        pixmap = status_icon_pixmap(self._paused, _STATUS_ICON_SIZE)
        if pixmap.isNull():
            return
        painter = QPainter(self)
        x = 17 - pixmap.width() // 2
        y = (self.height() - pixmap.height()) // 2
        painter.drawPixmap(x, y, pixmap)


class QueuePanel(QWidget):
    """Side panel showing the play queue: the current track and what comes next.

    Rebuilt from the controller whenever the queue or the current track changes. The
    queue is small, so plain row widgets are used rather than a model and a view, which
    keeps the click and remove handling simple.
    """

    def __init__(self, mf: "MainForm", *args, **kwargs):
        """Build the panel, hidden until toggled.

        :param mf: Main form, for the playback controller.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.mf = mf
        self.setVisible(False)
        self.setObjectName("QueueRoot")
        self.setStyleSheet(f"""
        QWidget#QueueRoot {{ background-color: {AppColorSchemes.FILE_LIST_ITEM_BODY}; }}
        QLabel#Header {{ color: #111111; }}
        QLabel#Section {{ color: #777777; }}
        QLabel#Empty {{ color: #888888; }}
        QPushButton#Close {{
            background-color: transparent; border: 0px; color: #555555; font-size: 16px;
        }}
        QPushButton#Close:hover {{ color: #111111; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 6, 10)
        root.setSpacing(8)

        header = QHBoxLayout()
        self.header_label = QLabel("", self)
        self.header_label.setObjectName("Header")
        header_font = QFont("Arima")
        header_font.setPointSize(13)
        header_font.setBold(True)
        self.header_label.setFont(header_font)
        self.close_button = QPushButton("✕", self)
        self.close_button.setObjectName("Close")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(lambda: self.setVisible(False))
        header.addWidget(self.header_label, 1)
        header.addWidget(self.close_button)
        root.addLayout(header)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(DEFAULT_SCROLLBAR_STYLE)
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(2)
        self.rows_layout.addStretch(1)
        self.scroll_area.setWidget(self.rows_container)
        root.addWidget(self.scroll_area, 1)

        self.empty_label = QLabel("", self)
        self.empty_label.setObjectName("Empty")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.empty_label)

        self.mf.playback.queueChanged.connect(self.refresh)
        self.mf.playback.currentTrackChanged.connect(self._on_current_changed)
        self.mf.playback.playbackStateChanged.connect(self._on_state_changed)

        self.retranslate_ui()

    def changeEvent(self, event: QEvent) -> None:
        """Reapply texts on a language change.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self) -> None:
        """Apply the current translation and rebuild the rows.

        :returns: None.
        """
        self.header_label.setText(self.tr("Queue"))
        self.refresh()

    def toggle(self) -> None:
        """Show or hide the panel, refreshing when it appears.

        :returns: None.
        """
        self.setVisible(not self.isVisible())
        if self.isVisible():
            self.refresh()

    @QtCore.pyqtSlot(int)
    def _on_current_changed(self, _track_id: int) -> None:
        """Rebuild when the current track changes.

        :param _track_id: Current track id, unused.
        :returns: None.
        """
        self.refresh()

    def _on_state_changed(self, _state) -> None:
        """Rebuild when play or pause changes, to swap the marker glyph.

        :param _state: New state, unused.
        :returns: None.
        """
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the rows from the current queue.

        :returns: None.
        """
        if not self.isVisible():
            return
        self._clear_rows()

        queue = self.mf.playback.queue
        ids = queue.items
        if not ids:
            self.empty_label.setText(self.tr("The queue is empty"))
            self.empty_label.setVisible(True)
            self.scroll_area.setVisible(False)
            return
        self.empty_label.setVisible(False)
        self.scroll_area.setVisible(True)

        session = create_session()
        try:
            info = library_repo.get_queue_tracks(session, ids)
        finally:
            session.close()

        current_index = queue.index
        paused = self.mf.playback.state is PlayerState.PAUSE

        if 0 <= current_index < len(ids):
            self._add_section(self.tr("Now playing"))
            self._add_row(current_index, ids[current_index], info, is_current=True,
                          paused=paused, removable=False)
        upcoming = list(range(current_index + 1, len(ids)))
        if upcoming:
            self._add_section(self.tr("Next up"))
            for position in upcoming:
                self._add_row(position, ids[position], info, is_current=False,
                              paused=False, removable=True)

    def _add_section(self, text: str) -> None:
        """Add a section heading row.

        :param text: Heading text.
        :returns: None.
        """
        label = QLabel(text, self.rows_container)
        label.setObjectName("Section")
        font = QFont("Arima")
        font.setPointSize(8)
        font.setBold(True)
        label.setFont(font)
        label.setContentsMargins(6, 6, 0, 2)
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, label)

    def _add_row(self, position: int, track_id: int, info: dict, is_current: bool,
                 paused: bool, removable: bool) -> None:
        """Add a track row.

        :param position: Queue position.
        :param track_id: Track id.
        :param info: Display info per id from the repository.
        :param is_current: Whether this is the current track.
        :param paused: Whether the current track is paused.
        :param removable: Whether the row shows a remove button.
        :returns: None.
        """
        track = info.get(track_id)
        title = track.title if track is not None else self.tr("Unknown track")
        artist = track.artist if track is not None else None
        duration = track.duration if track is not None else None
        row = QueueRow(position, track_id, title, artist, duration, is_current, paused, removable,
                       self.rows_container)
        row.clicked.connect(self._on_row_clicked)
        row.removeRequested.connect(self.mf.playback.remove_from_queue)
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)

    @QtCore.pyqtSlot(int)
    def _on_row_clicked(self, track_id: int) -> None:
        """Jump to the clicked track, or pause it when it is already the one playing.

        :param track_id: Track id of the clicked row.
        :returns: None.
        """
        if self.mf.playback.is_playing(track_id):
            self.mf.playback.toggle_pause()
        else:
            self.mf.playback.jump_to(track_id)

    def _clear_rows(self) -> None:
        """Remove every row and section, keeping the trailing stretch.

        :returns: None.
        """
        for i in reversed(range(self.rows_layout.count())):
            item = self.rows_layout.itemAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                self.rows_layout.removeItem(item)

    def paintEvent(self, event) -> None:
        """Draw background.

        :param event: Qt paint event.
        :returns: None.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(0, 0, self.width(), self.height(), QColor(AppColorSchemes.FILE_LIST_ITEM_BODY))
