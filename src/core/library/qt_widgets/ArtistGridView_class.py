from PyQt6 import QtCore

from src.core.library.ArtistGridModel_class import ArtistGridModel, ArtistRoles
from src.core.library.cover_cache import CoverLoader
from src.core.library.qt_widgets.ArtistTileDelegate_class import ArtistTileDelegate
from src.core.library.qt_widgets.CoverGridView_class import CoverGridView


class ArtistGridView(CoverGridView):
    """The artist cover grid, a cover grid over the artist model and artist tile delegate.

    :signals: artistActivated (int) - artist id of a clicked tile
    """
    artistActivated = QtCore.pyqtSignal(int)

    def __init__(self, cover_loader: CoverLoader, *args, **kwargs):
        """Build the artist grid.

        :param cover_loader: Loader shared with the delegate.
        :returns: None.
        """
        super().__init__(cover_loader, ArtistGridModel(), ArtistTileDelegate(cover_loader),
                         ArtistRoles.ARTIST_ID, ArtistRoles.COVER_HASH, *args, **kwargs)
        self.itemActivated.connect(self.artistActivated)

    def model(self) -> ArtistGridModel:
        """The typed artist model backing the grid.

        :returns: ArtistGridModel - The model.
        """
        return self._model
