from typing import List, Optional, TYPE_CHECKING

from PyQt6 import QtCore
from PyQt6.QtCore import QEvent, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from src.api.db.db_handler import create_session
from src.api.db import library_repo
from src.core.library.AlbumTracksModel_class import AlbumTracksModel
from src.core.library.qt_widgets.TrackListView_class import TrackListView
from src.core.library.qt_widgets.TrackRowDelegate_class import TrackRowDelegate
from src.enums import PlayerState, TrackSort
from src.global_styles import AppColorSchemes, DEFAULT_SCROLLBAR_STYLE

if TYPE_CHECKING:
    from src.forms import MainForm

# Debounce so a search reloads once the user pauses, not on every keystroke
_SEARCH_DEBOUNCE_MS = 250


class AllTracksPage(QWidget):
    """The flat list of every track in the library, the home of loose tracks.

    A track with no album never appears on the album grid; without this list it would
    only live in the capped recent list and drop out of reach as more are added. The
    list is a model and delegate over TrackRow tuples, so it stays light on a big
    library where a widget per row would stall the interface.
    """

    def __init__(self, mf: "MainForm", *args, **kwargs):
        """Build the page.

        :param mf: Main form, for the playback controller.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.mf = mf
        self._sort: TrackSort = TrackSort.TITLE

        self.setObjectName("AllTracksRoot")
        self.setStyleSheet(f"""
        QWidget#AllTracksRoot {{ background-color: {AppColorSchemes.FILE_LIST_BACKGROUND}; }}
        QLabel {{ color: #222222; background-color: transparent; }}
        QLineEdit {{
            background-color: {AppColorSchemes.FILE_LIST_ITEM_BODY}; border: 0px; border-radius: 6px;
            padding: 5px 10px; color: #111111;
        }}
        QComboBox {{
            background-color: {AppColorSchemes.FILE_LIST_ITEM_BODY}; border: 0px; border-radius: 6px;
            padding: 4px 10px; color: #111111; min-width: 130px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {AppColorSchemes.FILE_LIST_ITEM_BODY}; color: #111111;
            selection-background-color: {AppColorSchemes.BUTTON_HOVER};
        }}
        QListView {{ background-color: {AppColorSchemes.FILE_LIST_BACKGROUND}; border: 0px; outline: 0; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # region header
        header = QHBoxLayout()
        header.setSpacing(10)
        self.search_edit = QLineEdit(self)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        self.sort_label = QLabel(self)
        self.sort_combo = QComboBox(self)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        self.count_label = QLabel(self)
        count_font = QFont("Arima")
        count_font.setPointSize(9)
        self.count_label.setFont(count_font)
        header.addWidget(self.search_edit, 1)
        header.addWidget(self.sort_label)
        header.addWidget(self.sort_combo)
        header.addStretch(0)
        header.addWidget(self.count_label)
        root.addLayout(header)
        # endregion

        # region list
        self.model = AlbumTracksModel(self)
        self.delegate = TrackRowDelegate(self)
        self.list_view = TrackListView(self.mf, self)
        self.list_view.setModel(self.model)
        self.list_view.setItemDelegate(self.delegate)
        self.list_view.setStyleSheet(DEFAULT_SCROLLBAR_STYLE)
        self.list_view.playRequested.connect(self._on_track_activated)
        root.addWidget(self.list_view, 1)
        # endregion

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(_SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self.reload)

        # The controller drives which row is marked playing, the same source as everywhere
        self.mf.playback.currentTrackChanged.connect(self._on_current_track_changed)
        self.mf.playback.playbackStateChanged.connect(self._on_state_changed)

        self._build_sort_items()
        self.retranslate_ui()

    # region i18n
    def changeEvent(self, event: QEvent) -> None:
        """Reapply the texts when the application language changes.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self._build_sort_items()
            self.retranslate_ui()
        super().changeEvent(event)

    def _build_sort_items(self) -> None:
        """Fill the sort selector, keeping the current choice.

        :returns: None.
        """
        options = [
            (TrackSort.TITLE, self.tr("Title")),
            (TrackSort.ARTIST, self.tr("Artist")),
            (TrackSort.DATE_ADDED, self.tr("Recently added")),
            (TrackSort.DURATION, self.tr("Length")),
        ]
        self.sort_combo.blockSignals(True)
        self.sort_combo.clear()
        for value, label in options:
            self.sort_combo.addItem(label, value)
        index = self.sort_combo.findData(self._sort)
        self.sort_combo.setCurrentIndex(max(0, index))
        self.sort_combo.blockSignals(False)

    def retranslate_ui(self) -> None:
        """Apply the current translation to the controls.

        :returns: None.
        """
        self.search_edit.setPlaceholderText(self.tr("Search tracks"))
        self.sort_label.setText(self.tr("Sort:"))
        self._update_count()
    # endregion

    # region data
    def reload(self) -> None:
        """Reload the list from the library for the current search and sort.

        :returns: None.
        """
        search = self.search_edit.text().strip() or None
        session = create_session()
        try:
            rows = library_repo.list_tracks(session, search=search, sort=self._sort)
        finally:
            session.close()
        self.model.set_rows(rows)
        self.list_view.scrollToTop()
        self._sync_playing()
        self._update_count()

    def _update_count(self) -> None:
        """Refresh the track count in the header.

        :returns: None.
        """
        self.count_label.setText(self.tr("%n track(s)", "", self.model.rowCount()))
    # endregion

    # region controls
    def _on_search_changed(self, _text: str) -> None:
        """Restart the debounce timer on every keystroke.

        :param _text: Current text, unused.
        :returns: None.
        """
        self._search_timer.start()

    def _on_sort_changed(self, _index: int) -> None:
        """Apply a new sort and reload.

        :param _index: New combo index, unused, the value is read from the data.
        :returns: None.
        """
        value = self.sort_combo.currentData()
        if value is not None:
            self._sort = value
            self.reload()

    def _on_track_activated(self, track_id: int) -> None:
        """Play a track from the list, or pause it when it is already playing.

        The whole visible list becomes the context, so next and previous walk what the
        user is looking at, filtered and sorted as it is on screen.

        :param track_id: Track to play.
        :returns: None.
        """
        self.mf.playback.activate_track(self.model.track_ids(), track_id)
    # endregion

    # region playing status
    @QtCore.pyqtSlot(int)
    def _on_current_track_changed(self, _track_id: int) -> None:
        """Move the playing marker onto the current track.

        :param _track_id: Track now playing, unused, read from the controller.
        :returns: None.
        """
        self._sync_playing()

    def _on_state_changed(self, _state) -> None:
        """Refresh the marker when playback pauses or resumes.

        :param _state: New PlayerState, unused.
        :returns: None.
        """
        self._sync_playing()

    def _sync_playing(self) -> None:
        """Push the current track and pause flag into the delegate and repaint.

        :returns: None.
        """
        current = self.mf.playback.current_track_id
        paused = self.mf.playback.state is PlayerState.PAUSE
        self.delegate.set_current(current, paused)
        self.list_view.viewport().update()
    # endregion
