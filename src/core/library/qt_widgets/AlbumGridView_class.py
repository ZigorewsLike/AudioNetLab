from typing import TYPE_CHECKING

from PyQt6 import QtCore
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QMenu

from src.api.db import library_repo
from src.api.db.db_handler import create_session
from src.core.file_system.os_integration import reveal_in_file_manager
from src.core.library.AlbumGridModel_class import AlbumGridModel, AlbumRoles
from src.core.library.cover_cache import CoverLoader
from src.core.library.qt_widgets.AlbumTileDelegate_class import AlbumTileDelegate
from src.core.library.qt_widgets.CoverGridView_class import CoverGridView

if TYPE_CHECKING:
    from src.forms import MainForm


class AlbumGridView(CoverGridView):
    """The album cover grid, a cover grid over the album model and album tile delegate.

    Owns the tile context menu, so the library tab and the artist page get the same one.

    :signals: albumActivated (int) - album id of a clicked tile
    """
    albumActivated = QtCore.pyqtSignal(int)

    def __init__(self, mf: "MainForm", cover_loader: CoverLoader, *args, **kwargs):
        """Build the album grid.

        :param mf: Main form, for playback and the delete.
        :param cover_loader: Loader shared with the delegate.
        :returns: None.
        """
        super().__init__(cover_loader, AlbumGridModel(), AlbumTileDelegate(cover_loader),
                         AlbumRoles.ALBUM_ID, AlbumRoles.COVER_HASH, *args, **kwargs)
        self.mf = mf
        self.itemActivated.connect(self.albumActivated)
        self.itemMenuRequested.connect(self._show_menu)

    def model(self) -> AlbumGridModel:
        """The typed album model backing the grid.

        :returns: AlbumGridModel - The model.
        """
        return self._model

    def _show_menu(self, album_id: int, position: QPoint) -> None:
        """Open the context menu of a tile.

        :param album_id: Album of the tile.
        :param position: Point in global coordinates.
        :returns: None.
        """
        menu = QMenu(self)
        play_action = menu.addAction(self.tr("Play"))
        queue_action = menu.addAction(self.tr("Add to queue"))
        open_action = menu.addAction(self.tr("Open"))
        reveal_action = menu.addAction(self.tr("Show in file manager"))
        menu.addSeparator()
        delete_action = menu.addAction(self.tr("Remove album"))

        chosen = menu.exec(position)
        if chosen is None:
            return
        if chosen is play_action:
            self.mf.play_album(album_id)
        elif chosen is queue_action:
            self.mf.enqueue_album(album_id)
        elif chosen is open_action:
            self.albumActivated.emit(album_id)
        elif chosen is reveal_action:
            self._reveal(album_id)
        elif chosen is delete_action:
            self.mf.delete_album_from_library(album_id)

    @staticmethod
    def _reveal(album_id: int) -> None:
        """Show the folder of an album in the file manager.

        :param album_id: Album to reveal.
        :returns: None.
        """
        session = create_session()
        try:
            path = library_repo.get_album_first_path(session, album_id)
        finally:
            session.close()
        reveal_in_file_manager(path)