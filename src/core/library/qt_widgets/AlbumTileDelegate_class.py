from PyQt6.QtCore import QModelIndex

from src.core.library.AlbumGridModel_class import AlbumRoles
from src.core.library.qt_widgets.CoverTileDelegate_class import CoverTileDelegate


class AlbumTileDelegate(CoverTileDelegate):
    """Draws one album tile: a rounded-square cover, the title and an artist-and-year line."""

    ID_ROLE = AlbumRoles.ALBUM_ID
    COVER_HASH_ROLE = AlbumRoles.COVER_HASH
    TITLE_ROLE = AlbumRoles.TITLE
    CIRCULAR = False

    def _subtitle(self, index: QModelIndex) -> str:
        """Build the subtitle line of an album tile.

        :param index: Cell index.
        :returns: str - Artist and year, or a track count fallback.
        """
        artist = index.data(AlbumRoles.ARTIST)
        year = index.data(AlbumRoles.YEAR)
        if artist:
            return f"{artist} • {year}" if year else artist
        count = index.data(AlbumRoles.TRACK_COUNT) or 0
        # Kept a plain string, the tr() lives on the widget that owns the delegate
        return self.tr("%n track(s)", "", count)
