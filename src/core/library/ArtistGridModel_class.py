from typing import List, Optional

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt

from src.api.db.library_repo import ArtistRow


class ArtistRoles:
    """Item data roles of the artist grid, past Qt.UserRole so they never collide."""
    ARTIST_ID = Qt.ItemDataRole.UserRole + 1
    NAME = Qt.ItemDataRole.UserRole + 2
    COVER_HASH = Qt.ItemDataRole.UserRole + 3
    ALBUM_COUNT = Qt.ItemDataRole.UserRole + 4
    TRACK_COUNT = Qt.ItemDataRole.UserRole + 5


class ArtistGridModel(QAbstractListModel):
    """List model backing the artist grid.

    Holds ArtistRow tuples rather than ORM objects, the same as the album grid, so the
    whole set loads at once and the view can rely on a stable row count while it paints
    only the visible tiles.
    """

    def __init__(self, *args, **kwargs):
        """Create an empty model.

        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self._rows: List[ArtistRow] = []

    def set_rows(self, rows: List[ArtistRow]) -> None:
        """Replace the whole content with a new result from the repository.

        :param rows: Artists to show, already in the order they should appear.
        :returns: None.
        """
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def artist_at(self, row: int) -> Optional[ArtistRow]:
        """Read the artist of a row.

        :param row: Row index.
        :returns: ArtistRow - The artist, None when the row is out of range.
        """
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Number of artists, zero for any child (this is a flat list).

        :param parent: Parent index.
        :returns: int - Row count.
        """
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Return one field of one artist for the delegate.

        :param index: Cell index.
        :param role: Requested role.
        :returns: The value for the role, None when it does not apply.
        """
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]

        if role in (Qt.ItemDataRole.DisplayRole, ArtistRoles.NAME):
            return row.name
        if role == ArtistRoles.ARTIST_ID:
            return row.id
        if role == ArtistRoles.COVER_HASH:
            return row.cover_hash
        if role == ArtistRoles.ALBUM_COUNT:
            return row.album_count
        if role == ArtistRoles.TRACK_COUNT:
            return row.track_count
        return None
