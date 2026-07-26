from typing import Optional

from PyQt6.QtCore import QModelIndex, QPointF, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPolygonF
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from src.core.library.AlbumTracksModel_class import TrackRoles
from src.enums import PlayerState

# Accent used for the number and the status glyph of the current track
_ACCENT = QColor("#2f8f43")


class AlbumTrackDelegate(QStyledItemDelegate):
    """Draws one track row of the album page: status or number, title, format, length.

    The play or pause glyph is painted with the painter, not loaded from an icon, so the
    status shows without shipping transport icons. The view tells the delegate which
    track is current and whether it is paused; every other row shows its number.
    """

    ROW_HEIGHT = 46
    _NUMBER_WIDTH = 40
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
        self._number_font = QFont("Arima")
        self._number_font.setPointSize(10)
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

        # Left column: the status glyph for the current track, otherwise the number
        number_rect = QRect(rect.x(), rect.y(), self._NUMBER_WIDTH, rect.height())
        if is_current:
            self._draw_status(painter, number_rect)
        else:
            painter.setFont(self._number_font)
            painter.setPen(QColor("#8a8a8a") if not is_missing else QColor("#b06a6a"))
            number = index.data(TrackRoles.NUMBER)
            painter.drawText(number_rect, Qt.AlignmentFlag.AlignCenter, str(number if number else ""))

        text_left = rect.x() + self._NUMBER_WIDTH
        text_width = rect.width() - self._NUMBER_WIDTH - self._DURATION_WIDTH - self._PADDING

        # Title on top, the format line in grey below it
        painter.setFont(self._title_font)
        painter.setPen(QColor("#8a1f1f") if is_missing else (_ACCENT if is_current else QColor("#141414")))
        title = index.data(TrackRoles.TITLE) or ""
        metrics = painter.fontMetrics()
        painter.drawText(QRect(text_left, rect.y() + 5, text_width, 18),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         metrics.elidedText(title, Qt.TextElideMode.ElideRight, text_width))

        painter.setFont(self._sub_font)
        painter.setPen(QColor("#7a7a7a"))
        fmt = index.data(TrackRoles.FORMAT) or ""
        if is_missing:
            fmt = self.tr("File not found")
        metrics = painter.fontMetrics()
        painter.drawText(QRect(text_left, rect.y() + 23, text_width, 15),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         metrics.elidedText(fmt, Qt.TextElideMode.ElideRight, text_width))

        # Duration, right aligned
        painter.setFont(self._sub_font)
        painter.setPen(QColor("#6a6a6a"))
        duration_rect = QRect(rect.right() - self._DURATION_WIDTH, rect.y(),
                              self._DURATION_WIDTH - self._PADDING, rect.height())
        painter.drawText(duration_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         index.data(TrackRoles.DURATION) or "")

        painter.restore()

    def _draw_status(self, painter: QPainter, rect: QRect) -> None:
        """Draw the play triangle or the pause bars centred in a rect.

        :param painter: Active painter.
        :param rect: Cell to centre the glyph in.
        :returns: None.
        """
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_ACCENT)
        cx, cy = rect.center().x() + 1, rect.center().y() + 1
        size = 5
        if self._paused:
            painter.drawRect(cx - size, cy - size, 3, size * 2)
            painter.drawRect(cx + 2, cy - size, 3, size * 2)
        else:
            triangle = QPolygonF([QPointF(cx - size + 1, cy - size),
                                  QPointF(cx - size + 1, cy + size),
                                  QPointF(cx + size + 1, cy)])
            path = QPainterPath()
            path.addPolygon(triangle)
            painter.drawPath(path)
        painter.restore()
