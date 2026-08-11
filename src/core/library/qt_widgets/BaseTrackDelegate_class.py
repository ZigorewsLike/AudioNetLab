from PyQt6.QtCore import QModelIndex, QRect, QSize
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from src.function_lib.qt_utils import delete_icon_pixmap, status_icon_pixmap

# Edge length of the play or pause marker drawn in the left column
_STATUS_ICON_SIZE = 14

# Edge length of the delete marker drawn at the right end of a hovered row
_DELETE_ICON_SIZE = 16


class BaseTrackDelegate(QStyledItemDelegate):
    """What the two track row delegates have in common: the length and the delete button.

    The button is painted rather than being a widget per row, so a long list still costs
    only the rows on screen; the view hit-tests action_rect to catch a click on it. Its
    column is reserved whether or not the button shows, so nothing shifts on hover.
    """

    ROW_HEIGHT = 46
    _DURATION_WIDTH = 64
    _ACTION_WIDTH = 34
    _PADDING = 10

    def __init__(self, *args, **kwargs):
        """Create the delegate with nothing playing.

        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self._current_track_id: int = -1
        self._paused: bool = False

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

    @classmethod
    def action_rect(cls, row_rect: QRect) -> QRect:
        """Rect of the delete button at the right end of a row.

        :param row_rect: Rect of the whole row, as the view reports it.
        :returns: QRect - Cell the delete marker is drawn in and clicked in.
        """
        return QRect(row_rect.right() - cls._ACTION_WIDTH, row_rect.y(),
                     cls._ACTION_WIDTH, row_rect.height())

    def _text_width(self, row_rect: QRect, left_width: int) -> int:
        """Width left for the title and subtitle between the two columns.

        :param row_rect: Rect of the whole row.
        :param left_width: Width of the delegate's own left column.
        :returns: int - Width available for the text.
        """
        return row_rect.width() - left_width - self._DURATION_WIDTH - self._ACTION_WIDTH - self._PADDING

    def _duration_rect(self, row_rect: QRect) -> QRect:
        """Rect the length is right aligned in, left of the delete button.

        :param row_rect: Rect of the whole row.
        :returns: QRect - Cell of the length.
        """
        left = row_rect.right() - self._ACTION_WIDTH - self._DURATION_WIDTH
        return QRect(left, row_rect.y(), self._DURATION_WIDTH - self._PADDING, row_rect.height())

    def _draw_status(self, painter: QPainter, rect: QRect) -> None:
        """Draw the play or pause marker icon centred in a rect.

        :param painter: Active painter.
        :param rect: Cell to centre the marker in.
        :returns: None.
        """
        self._draw_centred(painter, rect, status_icon_pixmap(self._paused, _STATUS_ICON_SIZE))

    def _draw_action(self, painter: QPainter, rect: QRect) -> None:
        """Draw the delete marker icon centred in a rect.

        :param painter: Active painter.
        :param rect: Cell to centre the marker in.
        :returns: None.
        """
        self._draw_centred(painter, rect, delete_icon_pixmap(_DELETE_ICON_SIZE))

    @staticmethod
    def _draw_centred(painter: QPainter, rect: QRect, pixmap) -> None:
        """Draw a pixmap in the middle of a rect, skipping a missing icon file.

        :param painter: Active painter.
        :param rect: Cell to centre the pixmap in.
        :param pixmap: Pixmap to draw.
        :returns: None.
        """
        if pixmap.isNull():
            return
        x = rect.x() + (rect.width() - pixmap.width()) // 2
        y = rect.y() + (rect.height() - pixmap.height()) // 2
        painter.drawPixmap(x, y, pixmap)
