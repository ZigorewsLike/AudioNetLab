from typing import TYPE_CHECKING

from PyQt6 import QtCore
from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtGui import QKeySequence, QMouseEvent, QShortcut
from PyQt6.QtWidgets import QAbstractItemView, QListView, QMenu

from src.core.file_system.os_integration import reveal_in_file_manager
from src.core.library.AlbumTracksModel_class import TrackRoles
from src.core.library.qt_widgets.BaseTrackDelegate_class import BaseTrackDelegate

if TYPE_CHECKING:
    from src.forms import MainForm


class TrackListView(QListView):
    """The track list of the album page, the artist page and the flat all-tracks list.

    Carries what a row can do besides being clicked: the delete button the delegate
    paints at the right end of a hovered row, the context menu and the Delete key.
    Playing is left to the page, which owns the context the queue is filled from.

    :signals: playRequested (int) - track id to play in the page's own context
    """
    playRequested = QtCore.pyqtSignal(int)

    def __init__(self, mf: "MainForm", *args, **kwargs):
        """Build the list.

        :param mf: Main form, for the playback controller, the delete and the navigation.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.mf = mf
        self._album_navigation = True

        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setUniformItemSizes(True)
        self.setMouseTracking(True)  # The delete button follows the cursor
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self.clicked.connect(self._on_clicked)

        delete_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Delete), self)
        delete_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        delete_shortcut.activated.connect(self._delete_selected)

    def set_album_navigation(self, enabled: bool) -> None:
        """Show or hide the menu entry that opens the album of a track.

        :param enabled: False on the album page, where the entry leads nowhere.
        :returns: None.
        """
        self._album_navigation = enabled

    # region mouse
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Catch a click on the delete button, swallowing it so the row is not played.

        :param event: Qt mouse event.
        :returns: None.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.pos())
            if index.isValid() and self._on_action(index, event.pos()):
                self._delete_track(index)
                return
        super().mousePressEvent(event)

    def _on_action(self, index: QModelIndex, position) -> bool:
        """Whether a point inside a row falls on its delete button.

        :param index: Row under the cursor.
        :param position: Point in viewport coordinates.
        :returns: bool - True when the delete button was hit.
        """
        delegate = self.itemDelegate()
        if not isinstance(delegate, BaseTrackDelegate):
            return False
        return delegate.action_rect(self.visualRect(index)).contains(position)

    def _on_clicked(self, index: QModelIndex) -> None:
        """Ask the page to play the clicked track.

        :param index: Clicked row.
        :returns: None.
        """
        track_id = index.data(TrackRoles.TRACK_ID)
        if track_id is not None:
            self.playRequested.emit(int(track_id))
    # endregion

    # region menu
    def _show_menu(self, position) -> None:
        """Open the context menu of the row under the cursor.

        :param position: Point in viewport coordinates.
        :returns: None.
        """
        index = self.indexAt(position)
        if not index.isValid():
            return
        track_id = index.data(TrackRoles.TRACK_ID)
        if track_id is None:
            return
        self.setCurrentIndex(index)

        menu = QMenu(self)
        play_action = menu.addAction(self.tr("Play"))
        queue_action = menu.addAction(self.tr("Add to queue"))
        menu.addSeparator()
        album_action = None
        if self._album_navigation:
            album_action = menu.addAction(self.tr("Go to album"))
            album_action.setEnabled(index.data(TrackRoles.ALBUM_ID) is not None)
        reveal_action = menu.addAction(self.tr("Show in file manager"))
        reveal_action.setEnabled(bool(index.data(TrackRoles.PATH)))
        menu.addSeparator()
        delete_action = menu.addAction(self.tr("Remove from library"))

        chosen = menu.exec(self.viewport().mapToGlobal(position))
        if chosen is None:
            return
        if chosen is play_action:
            self.playRequested.emit(int(track_id))
        elif chosen is queue_action:
            self.mf.playback.enqueue([int(track_id)])
        elif album_action is not None and chosen is album_action:
            self._open_album(index)
        elif chosen is reveal_action:
            reveal_in_file_manager(index.data(TrackRoles.PATH))
        elif chosen is delete_action:
            self._delete_track(index)

    def _open_album(self, index: QModelIndex) -> None:
        """Show the album page of a track.

        :param index: Row of the track.
        :returns: None.
        """
        album_id = index.data(TrackRoles.ALBUM_ID)
        if album_id is not None:
            self.mf.library_widget.open_album(int(album_id))
    # endregion

    # region delete
    def _delete_selected(self) -> None:
        """Remove the selected track, for the Delete key.

        :returns: None.
        """
        index = self.currentIndex()
        if index.isValid():
            self._delete_track(index)

    def _delete_track(self, index: QModelIndex) -> None:
        """Remove one track from the library, without a confirmation.

        :param index: Row of the track.
        :returns: None.
        """
        track_id = index.data(TrackRoles.TRACK_ID)
        if track_id is not None:
            self.mf.delete_tracks_from_library([int(track_id)])
    # endregion