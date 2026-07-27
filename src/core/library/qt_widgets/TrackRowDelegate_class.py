from PyQt6.QtCore import QModelIndex, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from src.core.library.AlbumTracksModel_class import TrackRoles
from src.function_lib.qt_utils import status_icon_pixmap

# Accent used for the title of the current track
_ACCENT = QColor("#2f8f43")

# Edge length of the play or pause marker drawn in the status column
_STATUS_ICON_SIZE = 14


class TrackRowDelegate(QStyledItemDelegate):
    """Draws one row of the flat all-tracks list: status, title, artist and album, length.

    Unlike the album track delegate the left column carries no track number, since the
    list mixes tracks from every album; it shows the play or pause marker on the current
    track and stays empty otherwise. The subtitle names the artist and album so a track
    with no album is still placed, which is the whole point of this list.
    """

    ROW_HEIGHT = 50
    _STATUS_WIDTH = 34
    _DURATION_WIDTH = 64
    _PADDING = 10

    def __init__(self, *args, **kwargs):
        """Create the delegate.

        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self._current_track_id: int = -1
        self._paused: bool = False

        self._title_font = QFont("Arima")
        self._title_font.setPointSize(10)
        self._sub_font = QFont("Arima")
        self._sub_font.setPointSize(8)

    def set_current(self, track_id: int, paused: bool) -> None:
        """Set which track is playing and whether it is paused.

        :param track_id: Current track id, -1 for none.
        :param paused: True when the current track is paused rather than playing.
        :returns: None.
        """
        self._current_track_id = track_id
        self._paused = paused

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        """Report a fixed row height.

        :param option: Style option.
        :param index: Cell index.
        :returns: QSize - Row size.
        """
        return QSize(option.rect.width(), self.ROW_HEIGHT)

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
        text_width = rect.width() - self._STATUS_WIDTH - self._DURATION_WIDTH - self._PADDING

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
        duration_rect = QRect(rect.right() - self._DURATION_WIDTH, rect.y(),
                              self._DURATION_WIDTH - self._PADDING, rect.height())
        painter.drawText(duration_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         index.data(TrackRoles.DURATION) or "")

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

    def _draw_status(self, painter: QPainter, rect: QRect) -> None:
        """Draw the play or pause marker icon centred in a rect.

        :param painter: Active painter.
        :param rect: Cell to centre the marker in.
        :returns: None.
        """
        pixmap = status_icon_pixmap(self._paused, _STATUS_ICON_SIZE)
        if pixmap.isNull():
            return
        x = rect.x() + (rect.width() - pixmap.width()) // 2
        y = rect.y() + (rect.height() - pixmap.height()) // 2
        painter.drawPixmap(x, y, pixmap)
