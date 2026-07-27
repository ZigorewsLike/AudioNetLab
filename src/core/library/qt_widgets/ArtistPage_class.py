from typing import List, Optional, TYPE_CHECKING

from PyQt6 import QtCore
from PyQt6.QtCore import QEvent, QModelIndex, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QListView, QPushButton,
                             QVBoxLayout, QWidget)

from src.api.db.db_handler import create_session
from src.api.db import library_repo
from src.core.library.AlbumTracksModel_class import AlbumTracksModel, TrackRoles
from src.core.library.cover_cache import CoverLoader
from src.core.library.qt_widgets.ArtistGridView_class import ArtistGridView
from src.core.library.qt_widgets.TrackRowDelegate_class import TrackRowDelegate
from src.core.library.qt_widgets.AlbumGridView_class import AlbumGridView
from src.core.library.qt_widgets.CoverTileDelegate_class import CoverTileDelegate
from src.enums import PlayerState, TrackSort
from src.global_styles import AppColorSchemes, DEFAULT_SCROLLBAR_STYLE

if TYPE_CHECKING:
    from src.forms import MainForm


class ArtistPage(QWidget):
    """Detail page of one artist: a header, the artist albums and their other tracks.

    The albums are the artist grid's square tiles reused. The tracks section lists every
    track credited to the artist that is not on one of those albums: loose singles with no
    album at all, and guest appearances on albums an album artist owns. Without it a
    featured singer whose only tracks sit on someone else's album would open to a blank
    page, since none of their tracks are on an album attributed to them. Play all queues
    every track of the artist in album order.

    :signals: backRequested () - the back button was pressed,
              albumActivated (int) - album id of a clicked album tile
    """
    backRequested = QtCore.pyqtSignal()
    albumActivated = QtCore.pyqtSignal(int)

    def __init__(self, mf: "MainForm", cover_loader: CoverLoader, *args, **kwargs):
        """Build the page.

        :param mf: Main form, for the playback controller.
        :param cover_loader: Cover loader shared with the rest of the library tab.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.mf = mf
        self._artist_id: Optional[int] = None
        self._artist = None
        self._track_ids: List[int] = []

        self.setObjectName("ArtistRoot")
        self.setStyleSheet(f"""
        QWidget#ArtistRoot {{ background-color: {AppColorSchemes.FILE_LIST_BACKGROUND}; }}
        QLabel {{ color: #141414; background-color: transparent; }}
        QLabel#ArtistTitle {{ color: #111111; }}
        QLabel#ArtistSub {{ color: #555555; }}
        QLabel#SectionLabel {{ color: #333333; }}
        QListView {{ background-color: {AppColorSchemes.FILE_LIST_BACKGROUND}; border: 0px; outline: 0; }}
        QPushButton {{
            background-color: {AppColorSchemes.FILE_LIST_ITEM_BODY}; border: 0px;
            border-radius: 6px; padding: 6px 16px; color: #111111;
        }}
        QPushButton:hover {{ background-color: {AppColorSchemes.BUTTON_HOVER}; }}
        QPushButton#PlayButton {{ background-color: #2f8f43; color: white; font-weight: bold; }}
        QPushButton#PlayButton:hover {{ background-color: #37a24d; }}
        """)

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
        self.title_label = QLabel("", self)
        self.title_label.setObjectName("ArtistTitle")
        title_font = QFont("Arima")
        title_font.setPointSize(22)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)

        self.subtitle_label = QLabel("", self)
        self.subtitle_label.setObjectName("ArtistSub")
        sub_font = QFont("Arima")
        sub_font.setPointSize(10)
        self.subtitle_label.setFont(sub_font)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.button_play = QPushButton("", self)
        self.button_play.setObjectName("PlayButton")
        self.button_play.clicked.connect(self._on_play_all)
        buttons.addWidget(self.button_play)
        buttons.addStretch(1)

        root.addWidget(self.title_label)
        root.addWidget(self.subtitle_label)
        root.addLayout(buttons)
        # endregion

        # region albums
        self.albums_label = QLabel("", self)
        self.albums_label.setObjectName("SectionLabel")
        section_font = QFont("Arima")
        section_font.setPointSize(12)
        section_font.setBold(True)
        self.albums_label.setFont(section_font)
        root.addWidget(self.albums_label)

        self.album_grid = AlbumGridView(cover_loader, self)
        self.album_grid.set_cover_size(CoverTileDelegate.COVER_SMALL)
        self.album_grid.albumActivated.connect(self.albumActivated)
        root.addWidget(self.album_grid, 3)
        # endregion

        # region tracks
        self.tracks_label = QLabel("", self)
        self.tracks_label.setObjectName("SectionLabel")
        self.tracks_label.setFont(section_font)
        root.addWidget(self.tracks_label)

        self.tracks_model = AlbumTracksModel(self)
        self.tracks_delegate = TrackRowDelegate(self)
        self.tracks_view = QListView(self)
        self.tracks_view.setModel(self.tracks_model)
        self.tracks_view.setItemDelegate(self.tracks_delegate)
        self.tracks_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tracks_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tracks_view.setUniformItemSizes(True)
        self.tracks_view.setMouseTracking(True)
        self.tracks_view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.tracks_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tracks_view.setStyleSheet(DEFAULT_SCROLLBAR_STYLE)
        self.tracks_view.clicked.connect(self._on_track_activated)
        root.addWidget(self.tracks_view, 2)
        # endregion

        # The controller drives which track row is marked playing, the same source everywhere
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
        """Apply the current translation to the static texts.

        :returns: None.
        """
        self.button_back.setText(self.tr("← Back"))
        self.button_play.setText(self.tr("Play all"))
        self.albums_label.setText(self.tr("Albums"))
        self.tracks_label.setText(self.tr("Tracks"))
        if self._artist_id is not None:
            self._apply_subtitle()
    # endregion

    # region data
    def load(self, artist_id: int) -> None:
        """Fill the page with an artist, their albums and their singles.

        :param artist_id: Artist id.
        :returns: None.
        """
        self._artist_id = artist_id
        session = create_session()
        try:
            artists = {a.id: a for a in library_repo.list_artists(session)}
            artist = artists.get(artist_id)
            albums = library_repo.list_albums(session, artist_id=artist_id)
            artist_tracks = library_repo.list_tracks(session, artist_id=artist_id,
                                                     sort=TrackSort.ALBUM)
        finally:
            session.close()
        if artist is None:
            return

        self._artist = artist
        self.title_label.setText(artist.name or self.tr("Unknown artist"))
        self._apply_subtitle()

        self.album_grid.model().set_rows(albums)
        self.albums_label.setVisible(bool(albums))
        self.album_grid.setVisible(bool(albums))

        # Artist tracks not on the artist's own albums: loose singles and guest appearances
        own_album_ids = {a.id for a in albums}
        other_tracks = [t for t in artist_tracks if t.album_id not in own_album_ids]
        self.tracks_model.set_rows(other_tracks)
        self._track_ids = [t.id for t in other_tracks]
        has_tracks = bool(other_tracks)
        self.tracks_label.setVisible(has_tracks)
        self.tracks_view.setVisible(has_tracks)
        self._sync_playing()

    def _apply_subtitle(self) -> None:
        """Compose the album and track totals line.

        :returns: None.
        """
        artist = self._artist
        if artist is None:
            return
        parts = [self.tr("%n album(s)", "", artist.album_count or 0),
                 self.tr("%n track(s)", "", artist.track_count or 0)]
        self.subtitle_label.setText("  ·  ".join(parts))
    # endregion

    # region actions
    def _on_play_all(self) -> None:
        """Queue every track of the artist in album order and play from the top.

        :returns: None.
        """
        if self._artist_id is None:
            return
        session = create_session()
        try:
            tracks = library_repo.list_tracks(session, artist_id=self._artist_id, sort=TrackSort.ARTIST)
        finally:
            session.close()
        ids = [t.id for t in tracks]
        if ids:
            self.mf.playback.play_context(ids, 0)

    def _on_track_activated(self, index: QModelIndex) -> None:
        """Play the clicked track, or pause it when it is already playing.

        :param index: Clicked row.
        :returns: None.
        """
        track_id = index.data(TrackRoles.TRACK_ID)
        if track_id is not None:
            self.mf.playback.activate_track(self._track_ids, int(track_id))
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
        """Push the current track and pause flag into the tracks delegate and repaint.

        :returns: None.
        """
        current = self.mf.playback.current_track_id
        paused = self.mf.playback.state is PlayerState.PAUSE
        self.tracks_delegate.set_current(current, paused)
        self.tracks_view.viewport().update()
    # endregion
