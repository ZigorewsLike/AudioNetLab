from PyQt6 import QtCore

from src.core.library.AlbumGridModel_class import AlbumGridModel, AlbumRoles
from src.core.library.cover_cache import CoverLoader
from src.core.library.qt_widgets.AlbumTileDelegate_class import AlbumTileDelegate
from src.core.library.qt_widgets.CoverGridView_class import CoverGridView


class AlbumGridView(CoverGridView):
    """The album cover grid, a cover grid over the album model and album tile delegate.

    :signals: albumActivated (int) - album id of a clicked tile
    """
    albumActivated = QtCore.pyqtSignal(int)

    def __init__(self, cover_loader: CoverLoader, *args, **kwargs):
        """Build the album grid.

        :param cover_loader: Loader shared with the delegate.
        :returns: None.
        """
        super().__init__(cover_loader, AlbumGridModel(), AlbumTileDelegate(cover_loader),
                         AlbumRoles.ALBUM_ID, AlbumRoles.COVER_HASH, *args, **kwargs)
        # Kept as the album-specific name the library tab already connects to
        self.itemActivated.connect(self.albumActivated)

    def model(self) -> AlbumGridModel:
        """The typed album model backing the grid.

        :returns: AlbumGridModel - The model.
        """
        return self._model
