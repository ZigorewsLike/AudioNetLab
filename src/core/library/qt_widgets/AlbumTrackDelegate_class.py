from PyQt6.QtCore import QModelIndex, QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QStyle, QStyleOptionViewItem

from src.core.library.AlbumTracksModel_class import TrackRoles
from src.core.library.qt_widgets.BaseTrackDelegate_class import BaseTrackDelegate

# Accent used for the title of the current track
_ACCENT = QColor("#2f8f43")


class AlbumTrackDelegate(BaseTrackDelegate):
    """Draws one track row of the album page: status or number, title, format, length.

    The view tells the delegate which track is current and whether it is paused; every
    other row shows its number.
    """

    ROW_HEIGHT = 46
    _NUMBER_WIDTH = 40

    def __init__(self, *args, **kwargs):
        """Create the delegate.

        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self._title_font = QFont("Arima")
        self._title_font.setPointSize(10)
        self._number_font = QFont("Arima")
        self._number_font.setPointSize(10)
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
        text_width = self._text_width(rect, self._NUMBER_WIDTH)

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
        painter.drawText(self._duration_rect(rect),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         index.data(TrackRoles.DURATION) or "")

        # The delete button only under the cursor, its column is reserved either way
        if hovered:
            self._draw_action(painter, self.action_rect(rect))

        painter.restore()
