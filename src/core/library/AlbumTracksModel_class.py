from typing import List, Optional

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt

from src.api.db.library_repo import TrackRow


class TrackRoles:
    """Item data roles of the album track list, past Qt.UserRole so they never collide."""
    TRACK_ID = Qt.ItemDataRole.UserRole + 1
    NUMBER = Qt.ItemDataRole.UserRole + 2
    TITLE = Qt.ItemDataRole.UserRole + 3
    DURATION = Qt.ItemDataRole.UserRole + 4
    FORMAT = Qt.ItemDataRole.UserRole + 5
    IS_MISSING = Qt.ItemDataRole.UserRole + 6
    ARTIST = Qt.ItemDataRole.UserRole + 7
    ALBUM = Qt.ItemDataRole.UserRole + 8


def format_duration(seconds: Optional[float]) -> str:
    """Format a length as m:ss, or h:mm:ss past an hour.

    :param seconds: Length in seconds, None when unknown.
    :returns: str - The formatted length, an em dash when unknown.
    """
    if not seconds or seconds < 0:
        return "—"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_track_format(row: TrackRow) -> str:
    """Build the per-track format line: codec, sample rate, bit depth, bitrate.

    Only the parts a track actually carries are shown, so an MP3 with no bit depth
    simply omits it.

    :param row: Track row.
    :returns: str - Format line, empty when nothing is known.
    """
    parts: List[str] = []
    if row.file_ext:
        parts.append(row.file_ext)
    if row.sample_rate:
        khz = row.sample_rate / 1000
        parts.append(f"{khz:.1f} kHz".replace(".0 kHz", " kHz"))
    if row.bits_per_sample:
        parts.append(f"{row.bits_per_sample}-bit")
    if row.bitrate:
        parts.append(f"{round(row.bitrate / 1000)} kbps")
    return " · ".join(parts)


class AlbumTracksModel(QAbstractListModel):
    """List model for the track block of the album page.

    One row per track, in album order. Holds TrackRow tuples read once from the
    repository, not ORM objects, the same as the album grid.
    """

    def __init__(self, *args, **kwargs):
        """Create an empty model.

        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self._rows: List[TrackRow] = []

    def set_rows(self, rows: List[TrackRow]) -> None:
        """Replace the content with the tracks of an album.

        :param rows: Track rows in play order.
        :returns: None.
        """
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def track_at(self, row: int) -> Optional[TrackRow]:
        """Read the track of a row.

        :param row: Row index.
        :returns: TrackRow - The track, None when out of range.
        """
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def track_ids(self) -> List[int]:
        """Ids of every track in order, for handing the album to the queue.

        :returns: List[int] - Track ids.
        """
        return [row.id for row in self._rows]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Number of tracks.

        :param parent: Parent index.
        :returns: int - Row count.
        """
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Return one field of one track for the delegate.

        :param index: Cell index.
        :param role: Requested role.
        :returns: The value for the role, None when it does not apply.
        """
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]

        if role in (Qt.ItemDataRole.DisplayRole, TrackRoles.TITLE):
            return row.title
        if role == TrackRoles.TRACK_ID:
            return row.id
        if role == TrackRoles.NUMBER:
            return row.track_no if row.track_no else index.row() + 1
        if role == TrackRoles.DURATION:
            return format_duration(row.duration)
        if role == TrackRoles.FORMAT:
            return format_track_format(row)
        if role == TrackRoles.IS_MISSING:
            return row.is_missing
        if role == TrackRoles.ARTIST:
            return row.artist
        if role == TrackRoles.ALBUM:
            return row.album
        return None
