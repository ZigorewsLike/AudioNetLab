from PyQt6.QtCore import QModelIndex, QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QStyle, QStyleOptionViewItem

from src.core.library.AlbumTracksModel_class import TrackRoles
from src.core.library.qt_widgets.BaseTrackDelegate_class import BaseTrackDelegate

# Accent used for the title of the current track
_ACCENT = QColor("#2f8f43")


class TrackRowDelegate(BaseTrackDelegate):
    """Draws one row of the flat all-tracks list: status, title, artist and album, length.

    Unlike the album track delegate the left column carries no track number, since the
    list mixes tracks from every album; it shows the play or pause marker on the current
    track and stays empty otherwise. The subtitle names the artist and album so a track
    with no album is still placed, which is the whole point of this list.
    """

    ROW_HEIGHT = 50
    _STATUS_WIDTH = 34

    def __init__(self, *args, **kwargs):
        """Create the delegate.

        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self._title_font = QFont("Arima")
        self._title_font.setPointSize(10)
        self._sub_font = QFont("Arima")
        self._sub_font.setPointSize(8)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        """Draw one track row.

        :param painter: Painter clipped to the row.
        :param option: Style option with the state and the rect.
        :param index: Cell index.
        :returns: None.
        """
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = option.rect
        track_id = index.data(TrackRoles.TRACK_ID)
        is_current = track_id == self._current_track_id and self._current_track_id != -1
        is_missing = bool(index.data(TrackRoles.IS_MISSING))
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if selected or hovered or is_current:
            painter.fillRect(rect, QColor(0, 0, 0, 40 if selected else 22))

        # Status column: the play or pause marker on the current track, empty otherwise
        if is_current:
            status_rect = QRect(rect.x(), rect.y(), self._STATUS_WIDTH, rect.height())
            self._draw_status(painter, status_rect)

        text_left = rect.x() + self._STATUS_WIDTH
        text_width = self._text_width(rect, self._STATUS_WIDTH)

        # Title on top, the artist and album line in grey below it
        painter.setFont(self._title_font)
        painter.setPen(QColor("#8a1f1f") if is_missing else (_ACCENT if is_current else QColor("#141414")))
        title = index.data(TrackRoles.TITLE) or ""
        metrics = painter.fontMetrics()
        painter.drawText(QRect(text_left, rect.y() + 7, text_width, 18),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         metrics.elidedText(title, Qt.TextElideMode.ElideRight, text_width))

        painter.setFont(self._sub_font)
        painter.setPen(QColor("#7a7a7a"))
        if is_missing:
            subtitle = self.tr("File not found")
        else:
            subtitle = self._subtitle(index)
        metrics = painter.fontMetrics()
        painter.drawText(QRect(text_left, rect.y() + 26, text_width, 15),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         metrics.elidedText(subtitle, Qt.TextElideMode.ElideRight, text_width))

        # Duration, right aligned
        painter.setFont(self._sub_font)
        painter.setPen(QColor("#6a6a6a"))
        painter.drawText(self._duration_rect(rect),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         index.data(TrackRoles.DURATION) or "")

        # The delete button only under the cursor, its column is reserved either way
        if hovered:
            self._draw_action(painter, self.action_rect(rect))

        painter.restore()

    def _subtitle(self, index: QModelIndex) -> str:
        """Compose the artist and album line, falling back to the format when both are absent.

        :param index: Cell index.
        :returns: str - The subtitle, never blank so the row keeps its two lines.
        """
        parts = [value for value in (index.data(TrackRoles.ARTIST), index.data(TrackRoles.ALBUM)) if value]
        if parts:
            return "  ·  ".join(parts)
        # A loose track with no artist or album still gets a line, its format
        return index.data(TrackRoles.FORMAT) or self.tr("Unknown artist")
