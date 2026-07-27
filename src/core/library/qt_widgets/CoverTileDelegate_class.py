from typing import Dict, Optional

from PyQt6.QtCore import QModelIndex, QRect, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from src.core.library.cover_cache import CoverCache, CoverLoader
from src.function_lib.math_lib import fixed_hash
from src.global_constants import RESOURCE_ICON_DIR

# Number of bundled placeholder covers, track_default_cover_1..N.png
_PLACEHOLDER_COUNT = 6


class CoverTileDelegate(QStyledItemDelegate):
    """Base delegate for a wrapping grid of cover tiles: album tiles and artist tiles.

    It owns everything the two share: the tile geometry, the async cover request with a
    stable placeholder fallback, the hover and selection card, and the two-line text
    block. A subclass sets which roles carry the id, the cover hash and the title, whether
    the cover is a circle or a rounded square, and composes its own subtitle. A delegate
    is used instead of a widget per item so the view paints only the tiles on screen and a
    grid of thousands scrolls without building an extra object per row.
    """

    # Named cover edges in pixels
    COVER_SMALL = 130
    COVER_MEDIUM = 180
    COVER_LARGE = 260

    # Tile-size slider range, default and step, cover edge in pixels
    TILE_MIN_PX = 100
    TILE_MAX_PX = 180
    TILE_DEFAULT_PX = 180
    TILE_STEP_PX = 10

    _PADDING = 10
    _TEXT_HEIGHT = 42  # Two lines under the cover
    _CORNER = 8

    # Overridden by the subclass: the item data roles it stores its fields under
    ID_ROLE: int = 0
    COVER_HASH_ROLE: int = 0
    TITLE_ROLE: int = 0
    # A circular cover marks an artist apart from the square album tiles
    CIRCULAR: bool = False
    TEXT_ALIGN = Qt.AlignmentFlag.AlignLeft

    def __init__(self, cover_loader: CoverLoader, *args, **kwargs):
        """Create the delegate.

        :param cover_loader: Loader the tiles pull their covers from.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self._loader = cover_loader
        self._cover_px: int = self.COVER_MEDIUM
        self._placeholders: Dict[int, QPixmap] = {}  # index -> scaled placeholder

        self._title_font = QFont("Arima")
        self._title_font.setPointSize(10)
        self._title_font.setBold(True)
        self._subtitle_font = QFont("Arima")
        self._subtitle_font.setPointSize(8)

    def set_cover_size(self, cover_px: int) -> None:
        """Set the cover edge length the tiles are drawn at.

        :param cover_px: Cover edge in pixels.
        :returns: None.
        """
        if cover_px != self._cover_px:
            self._cover_px = cover_px
            self._placeholders.clear()  # They are scaled to the cover size

    def current_cover_size(self) -> int:
        """Cover edge length the tiles are currently drawn at.

        :returns: int - Cover edge in pixels.
        """
        return self._cover_px

    def tile_size(self) -> QSize:
        """Size of one tile at the current cover size.

        :returns: QSize - Tile size including the padding and the text.
        """
        width = self._cover_px + self._PADDING * 2
        height = self._cover_px + self._PADDING * 2 + self._TEXT_HEIGHT
        return QSize(width, height)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        """Report the tile size to the view.

        :param option: Style option.
        :param index: Cell index.
        :returns: QSize - Tile size.
        """
        return self.tile_size()

    def _placeholder(self, item_id: int) -> QPixmap:
        """Return a stable placeholder cover for an item without artwork.

        The same item always gets the same one, picked from its id, so the grid does
        not reshuffle its placeholders on every repaint.

        :param item_id: Item id.
        :returns: QPixmap - Placeholder scaled to the cover size.
        """
        index = fixed_hash(str(item_id)) % _PLACEHOLDER_COUNT
        cached = self._placeholders.get(index)
        if cached is not None:
            return cached
        pixmap = QPixmap(f"{RESOURCE_ICON_DIR}track_default_cover_{index + 1}.png")
        if not pixmap.isNull():
            pixmap = pixmap.scaled(self._cover_px, self._cover_px,
                                   Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                   Qt.TransformationMode.SmoothTransformation)
        self._placeholders[index] = pixmap
        return pixmap

    def _cover(self, item_id: int, cover_hash: Optional[str]) -> QPixmap:
        """Return the cover to draw, requesting a real one and falling back meanwhile.

        :param item_id: Item id, selects the placeholder.
        :param cover_hash: Hash of the cover, None when there is no artwork.
        :returns: QPixmap - The cover or a placeholder.
        """
        if cover_hash:
            pixmap = self._loader.request(cover_hash, self._cover_px)
            if pixmap is not None and not pixmap.isNull():
                return pixmap
        return self._placeholder(item_id)

    def cover_size_for_repaint(self) -> int:
        """Cache size the grid draws at, used to filter which coverReady signals matter.

        :returns: int - Nearest cached cover size.
        """
        return CoverCache.nearest_size(self._cover_px)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        """Draw one tile.

        :param painter: Painter clipped to the tile.
        :param option: Style option with the state and the rect.
        :param index: Cell index.
        :returns: None.
        """
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        # Card background, only drawn when the tile is picked out
        if selected or hovered:
            card = QRectF(rect.adjusted(4, 4, -4, -4))
            path = QPainterPath()
            path.addRoundedRect(card, self._CORNER, self._CORNER)
            painter.fillPath(path, QColor(0, 0, 0, 60 if selected else 30))

        cover_x = rect.x() + (rect.width() - self._cover_px) // 2
        cover_y = rect.y() + self._PADDING
        cover_rect = QRect(cover_x, cover_y, self._cover_px, self._cover_px)

        pixmap = self._cover(index.data(self.ID_ROLE), index.data(self.COVER_HASH_ROLE))
        self._draw_cover(painter, cover_rect, pixmap)

        text_left = rect.x() + self._PADDING
        text_width = rect.width() - self._PADDING * 2
        title_y = cover_y + self._cover_px + 4

        # Title, elided so a long name does not spill out of the tile
        painter.setFont(self._title_font)
        painter.setPen(QColor("#111111"))
        title = index.data(self.TITLE_ROLE) or ""
        metrics = painter.fontMetrics()
        elided = metrics.elidedText(title, Qt.TextElideMode.ElideRight, text_width)
        painter.drawText(QRect(text_left, title_y, text_width, 18),
                         self.TEXT_ALIGN | Qt.AlignmentFlag.AlignVCenter, elided)

        # Subtitle composed by the subclass
        painter.setFont(self._subtitle_font)
        painter.setPen(QColor("#555555"))
        subtitle = self._subtitle(index)
        metrics = painter.fontMetrics()
        elided = metrics.elidedText(subtitle, Qt.TextElideMode.ElideRight, text_width)
        painter.drawText(QRect(text_left, title_y + 18, text_width, 16),
                         self.TEXT_ALIGN | Qt.AlignmentFlag.AlignVCenter, elided)

        painter.restore()

    def _draw_cover(self, painter: QPainter, rect: QRect, pixmap: QPixmap) -> None:
        """Draw the cover cropped to a rounded square, or a circle for an artist.

        :param painter: Active painter.
        :param rect: Square the cover fills.
        :param pixmap: Cover or placeholder.
        :returns: None.
        """
        path = QPainterPath()
        if self.CIRCULAR:
            path.addEllipse(QRectF(rect))
        else:
            path.addRoundedRect(QRectF(rect), self._CORNER, self._CORNER)
        painter.save()
        painter.setClipPath(path)
        if pixmap.isNull():
            painter.fillRect(rect, QColor("#C4C4C4"))
        else:
            # Fill the square by scaling the shorter side, the clip trims the overflow
            scaled = pixmap.scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                   Qt.TransformationMode.SmoothTransformation)
            offset_x = rect.x() + (rect.width() - scaled.width()) // 2
            offset_y = rect.y() + (rect.height() - scaled.height()) // 2
            painter.drawPixmap(offset_x, offset_y, scaled)
        painter.restore()
        # A hairline keeps a light cover from blending into the background
        painter.setPen(QColor(0, 0, 0, 30))
        painter.drawPath(path)

    def _subtitle(self, index: QModelIndex) -> str:
        """Compose the subtitle line, defined by the subclass.

        :param index: Cell index.
        :returns: str - The subtitle text.
        """
        raise NotImplementedError
