from typing import List, Optional

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt

from src.api.db.library_repo import AlbumRow


class AlbumRoles:
    """Item data roles of the album grid, past Qt.UserRole so they never collide."""
    ALBUM_ID = Qt.ItemDataRole.UserRole + 1
    TITLE = Qt.ItemDataRole.UserRole + 2
    ARTIST = Qt.ItemDataRole.UserRole + 3
    YEAR = Qt.ItemDataRole.UserRole + 4
    COVER_HASH = Qt.ItemDataRole.UserRole + 5
    TRACK_COUNT = Qt.ItemDataRole.UserRole + 6
    DURATION = Qt.ItemDataRole.UserRole + 7


class AlbumGridModel(QAbstractListModel):
    """List model backing the album grid.

    Holds the rows as plain AlbumRow tuples, not ORM objects: the whole library is
    loaded at once, and a tuple costs a fraction of the memory and build time of a
    mapped entity. Fifty thousand albums are a few megabytes, so nothing is loaded
    lazily and the view can rely on a stable row count.
    """

    def __init__(self, *args, **kwargs):
        """Create an empty model.

        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self._rows: List[AlbumRow] = []

    def set_rows(self, rows: List[AlbumRow]) -> None:
        """Replace the whole content with a new result from the repository.

        A full reset is used rather than diffing, because a re-sort or a search moves
        almost every row anyway, and a reset is what a QListView redraws fastest.

        :param rows: Albums to show, already in the order they should appear.
        :returns: None.
        """
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def album_at(self, row: int) -> Optional[AlbumRow]:
        """Read the album of a row.

        :param row: Row index.
        :returns: AlbumRow - The album, None when the row is out of range.
        """
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Number of albums, zero for any child (this is a flat list).

        :param parent: Parent index.
        :returns: int - Row count.
        """
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Return one field of one album for the delegate.

        :param index: Cell index.
        :param role: Requested role.
        :returns: The value for the role, None when it does not apply.
        """
        if not index.isValid():
            return None
        row = index.row()
        if not (0 <= row < len(self._rows)):
            return None
        album = self._rows[row]

        if role in (Qt.ItemDataRole.DisplayRole, AlbumRoles.TITLE):
            return album.title
        if role == AlbumRoles.ALBUM_ID:
            return album.id
        if role == AlbumRoles.ARTIST:
            return album.artist
        if role == AlbumRoles.YEAR:
            return album.year
        if role == AlbumRoles.COVER_HASH:
            return album.cover_hash
        if role == AlbumRoles.TRACK_COUNT:
            return album.track_count
        if role == AlbumRoles.DURATION:
            return album.duration
        if role == Qt.ItemDataRole.ToolTipRole:
            parts = [album.title]
            if album.artist:
                parts.append(album.artist)
            if album.year:
                parts.append(str(album.year))
            return " • ".join(parts)
        return None
