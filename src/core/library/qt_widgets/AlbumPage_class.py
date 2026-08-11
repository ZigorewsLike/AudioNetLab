from typing import Optional, TYPE_CHECKING

from PyQt6 import QtCore
from PyQt6.QtCore import QEvent, QModelIndex, Qt
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QListView, QPushButton,
                             QVBoxLayout, QWidget)

from src.api.db.db_handler import create_session
from src.api.db import library_repo
from src.core.library.AlbumTracksModel_class import AlbumTracksModel, TrackRoles, format_duration
from src.core.library.cover_cache import CoverCache
from src.core.file_system.os_integration import reveal_in_file_manager
from src.core.library.qt_widgets.AlbumTrackDelegate_class import AlbumTrackDelegate
from src.enums import TrackSort, PlayerState
from src.function_lib.math_lib import fixed_hash
from src.global_constants import RESOURCE_ICON_DIR
from src.global_styles import AppColorSchemes, DEFAULT_SCROLLBAR_STYLE

if TYPE_CHECKING:
    from src.forms import MainForm

_COVER_PX = 190
_PLACEHOLDER_COUNT = 6


class AlbumPage(QWidget):
    """Detail page of one album: a header block and the track list.

    The header shows the cover, title, artist and the album totals with a play button
    and a reveal-in-explorer button. The list below shows every track with its own
    number, format and length, and marks the one that is playing.

    :signals: backRequested () - the back button was pressed
    """
    backRequested = QtCore.pyqtSignal()

    def __init__(self, mf: "MainForm", *args, **kwargs):
        """Build the page.

        :param mf: Main form, for the playback controller and revealing files.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.mf = mf
        self._album_id: Optional[int] = None
        self._first_path: Optional[str] = None
        self._album = None       # AlbumRow of the loaded album
        self._tracks = []        # TrackRow list of the loaded album

        self.setStyleSheet(f"""
        QWidget#AlbumRoot {{ background-color: {AppColorSchemes.FILE_LIST_BACKGROUND}; }}
        QLabel {{ color: #141414; background-color: transparent; }}
        QLabel#AlbumTitle {{ color: #111111; }}
        QLabel#AlbumSub {{ color: #555555; }}
        QListView {{ background-color: {AppColorSchemes.FILE_LIST_BACKGROUND}; border: 0px; outline: 0; }}
        QPushButton {{
            background-color: {AppColorSchemes.FILE_LIST_ITEM_BODY}; border: 0px;
            border-radius: 6px; padding: 6px 16px; color: #111111;
        }}
        QPushButton:hover {{ background-color: {AppColorSchemes.BUTTON_HOVER}; }}
        QPushButton#PlayButton {{ background-color: #2f8f43; color: white; font-weight: bold; }}
        QPushButton#PlayButton:hover {{ background-color: #37a24d; }}
        """)
        self.setObjectName("AlbumRoot")

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(10)

        # region back bar
        self.button_back = QPushButton("", self)
        self.button_back.setFixedWidth(90)
        self.button_back.clicked.connect(self.backRequested)
        back_bar = QHBoxLayout()
        back_bar.addWidget(self.button_back)
        back_bar.addStretch(1)
        root.addLayout(back_bar)
        # endregion

        # region header
        header = QHBoxLayout()
        header.setSpacing(16)

        self.cover_label = QLabel(self)
        self.cover_label.setFixedSize(_COVER_PX, _COVER_PX)
        self.cover_label.setScaledContents(True)

        info = QVBoxLayout()
        info.setSpacing(6)
        self.title_label = QLabel("", self)
        self.title_label.setObjectName("AlbumTitle")
        title_font = QFont("Arima")
        title_font.setPointSize(20)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)

        self.subtitle_label = QLabel("", self)
        self.subtitle_label.setObjectName("AlbumSub")
        sub_font = QFont("Arima")
        sub_font.setPointSize(10)
        self.subtitle_label.setFont(sub_font)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.button_play = QPushButton("", self)
        self.button_play.setObjectName("PlayButton")
        self.button_play.clicked.connect(self._on_play)
        self.button_reveal = QPushButton("", self)
        self.button_reveal.clicked.connect(self._on_reveal)
        buttons.addWidget(self.button_play)
        buttons.addWidget(self.button_reveal)
        buttons.addStretch(1)

        info.addStretch(1)
        info.addWidget(self.title_label)
        info.addWidget(self.subtitle_label)
        info.addSpacing(6)
        info.addLayout(buttons)
        info.addStretch(1)

        header.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignTop)
        header.addLayout(info, 1)
        root.addLayout(header)
        # endregion

        # region track list
        self.model = AlbumTracksModel(self)
        self.delegate = AlbumTrackDelegate(self)
        self.track_view = QListView(self)
        self.track_view.setModel(self.model)
        self.track_view.setItemDelegate(self.delegate)
        self.track_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.track_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.track_view.setUniformItemSizes(True)
        self.track_view.setMouseTracking(True)
        self.track_view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.track_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.track_view.setStyleSheet(DEFAULT_SCROLLBAR_STYLE)
        # A single click plays the track, matching the single click that opens the album
        self.track_view.clicked.connect(self._on_track_activated)
        root.addWidget(self.track_view, 1)
        # endregion

        # The controller drives which row is marked playing
        self.mf.playback.currentTrackChanged.connect(self._on_current_track_changed)
        self.mf.playback.playbackStateChanged.connect(self._on_state_changed)

        self.retranslate_ui()

    # region i18n
    def changeEvent(self, event: QEvent) -> None:
        """Reapply the texts on a language change.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self) -> None:
        """Apply the current translation to the buttons.

        :returns: None.
        """
        self.button_back.setText(self.tr("← Back"))
        self.button_play.setText(self.tr("Play"))
        self.button_reveal.setText(self.tr("Show in file manager"))
        if self._album_id is not None:
            self._apply_subtitle()
    # endregion

    # region data
    def load(self, album_id: int) -> None:
        """Fill the page with an album and its tracks.

        :param album_id: Album id.
        :returns: None.
        """
        self._album_id = album_id
        session = create_session()
        try:
            album = library_repo.get_album(session, album_id)
            tracks = library_repo.list_tracks(session, album_id=album_id, sort=TrackSort.ALBUM)
        finally:
            session.close()
        if album is None:
            return

        self._album = album
        self._tracks = tracks
        self.title_label.setText(album.title or self.tr("Unknown album"))
        self._apply_subtitle()
        self._set_cover(album.cover_hash, album_id)
        self.model.set_rows(tracks)
        # The view keeps its scroll offset between loads, reset it for the new album
        self.track_view.scrollToTop()
        self._first_path = next((t.path for t in tracks if t.path), None)
        self.button_reveal.setEnabled(self._first_path is not None)
        # Reflect the track that is currently playing, if it belongs to this album
        self._sync_playing()

    def _apply_subtitle(self) -> None:
        """Compose the artist, year and totals line.

        :returns: None.
        """
        album = getattr(self, "_album", None)
        if album is None:
            return
        parts = []
        if album.artist:
            parts.append(album.artist)
        if album.year:
            parts.append(str(album.year))
        parts.append(self.tr("%n track(s)", "", album.track_count or 0))
        if album.duration:
            parts.append(format_duration(album.duration))
        self.subtitle_label.setText("  ·  ".join(parts))

    def _set_cover(self, cover_hash: Optional[str], album_id: int) -> None:
        """Show the album cover, or a stable placeholder.

        :param cover_hash: Hash of the cover, None when the album has none.
        :param album_id: Album id, picks the placeholder.
        :returns: None.
        """
        pixmap = CoverCache.load_pixmap(cover_hash, _COVER_PX) if cover_hash else None
        if pixmap is None or pixmap.isNull():
            index = fixed_hash(str(album_id)) % _PLACEHOLDER_COUNT
            pixmap = QPixmap(f"{RESOURCE_ICON_DIR}track_default_cover_{index + 1}.png")
        self.cover_label.setPixmap(pixmap)
    # endregion

    # region actions
    def _on_play(self) -> None:
        """Play the whole album from the top.

        :returns: None.
        """
        ids = self.model.track_ids()
        if ids:
            self.mf.playback.play_context(ids, 0)

    def _on_track_activated(self, index: QModelIndex) -> None:
        """Play the clicked track, or pause it when it is already playing.

        :param index: Clicked row.
        :returns: None.
        """
        track_id = index.data(TrackRoles.TRACK_ID)
        if track_id is not None:
            self.mf.playback.activate_track(self.model.track_ids(), int(track_id))

    def _on_reveal(self) -> None:
        """Open the album folder in the system file manager.

        :returns: None.
        """
        reveal_in_file_manager(self._first_path)
    # endregion

    # region playing status
    @QtCore.pyqtSlot(int)
    def _on_current_track_changed(self, track_id: int) -> None:
        """Move the playing marker onto the current track.

        :param track_id: Track now playing.
        :returns: None.
        """
        self._sync_playing()

    def _on_state_changed(self, state) -> None:
        """Refresh the marker glyph when playback pauses or resumes.

        :param state: New PlayerState.
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
        self.track_view.viewport().update()
    # endregion
