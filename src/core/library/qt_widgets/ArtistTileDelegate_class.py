from PyQt6.QtCore import QModelIndex, Qt

from src.core.library.ArtistGridModel_class import ArtistRoles
from src.core.library.qt_widgets.CoverTileDelegate_class import CoverTileDelegate


class ArtistTileDelegate(CoverTileDelegate):
    """Draws one artist tile: a circular cover, the name and an album-and-track count line.

    The circular cover, centred under the name, sets an artist apart from the square
    album tiles at a glance, the way Spotify and AIMP do.
    """

    ID_ROLE = ArtistRoles.ARTIST_ID
    COVER_HASH_ROLE = ArtistRoles.COVER_HASH
    TITLE_ROLE = ArtistRoles.NAME
    CIRCULAR = True
    TEXT_ALIGN = Qt.AlignmentFlag.AlignHCenter

    def _subtitle(self, index: QModelIndex) -> str:
        """Build the subtitle line of an artist tile.

        :param index: Cell index.
        :returns: str - Album count and track count.
        """
        albums = index.data(ArtistRoles.ALBUM_COUNT) or 0
        tracks = index.data(ArtistRoles.TRACK_COUNT) or 0
        # Kept plain strings, the tr() lives on the widget that owns the delegate
        return f"{self.tr('%n album(s)', '', albums)}  ·  {self.tr('%n track(s)', '', tracks)}"
