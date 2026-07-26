from typing import Optional

from PyQt6 import QtCore
from PyQt6.QtCore import QModelIndex, QSize, Qt
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import QAbstractItemView, QListView

from src.core.library.AlbumGridModel_class import AlbumGridModel, AlbumRoles
from src.core.library.cover_cache import CoverCache, CoverLoader
from src.core.library.qt_widgets.AlbumTileDelegate_class import AlbumTileDelegate
from src.global_styles import AppColorSchemes, DEFAULT_SCROLLBAR_STYLE


class AlbumGridView(QListView):
    """Icon-mode list view that lays the album tiles out in a wrapping grid.

    The heavy lifting is left to QListView: it paints only the visible tiles, so the
    grid stays smooth on a library of thousands of albums. uniformItemSizes lets it
    skip measuring every row, batched layout keeps a resize from freezing, and the
    covers of tiles that scrolled past are dropped from the loader queue so a fast
    scroll never backs up behind covers nobody is looking at any more.

    :signals: albumActivated (int) - album id of a double-clicked or entered tile
    """
    albumActivated = QtCore.pyqtSignal(int)

    def __init__(self, cover_loader: CoverLoader, *args, **kwargs):
        """Build the grid.

        :param cover_loader: Loader shared with the delegate.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self._loader = cover_loader

        self._model = AlbumGridModel(self)
        self.setModel(self._model)

        self._delegate = AlbumTileDelegate(cover_loader, self)
        self.setItemDelegate(self._delegate)

        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)     # Re-wrap on resize
        self.setLayoutMode(QListView.LayoutMode.Batched)    # Lay out in chunks, stay responsive
        self.setBatchSize(200)
        self.setUniformItemSizes(True)                      # Every tile is the same size
        self.setMovement(QListView.Movement.Static)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setSpacing(6)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setMouseTracking(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self.setStyleSheet(f"""
        QListView {{
            background-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
            border: 0px;
            outline: 0;
        }}
        """ + DEFAULT_SCROLLBAR_STYLE)

        self._apply_grid_size()

        # A finished cover repaints just its tiles instead of the whole viewport
        self._loader.coverReady.connect(self._on_cover_ready)
        # Only doubleClicked: on Windows the activated signal also fires on a double
        # click, so connecting both would open the album twice on one gesture
        self.doubleClicked.connect(self._on_activated)

    def model(self) -> AlbumGridModel:
        """The typed model backing the grid.

        :returns: AlbumGridModel - The model.
        """
        return self._model

    def set_cover_size(self, cover_px: int) -> None:
        """Change the tile size and re-lay the grid.

        :param cover_px: Cover edge in pixels.
        :returns: None.
        """
        self._delegate.set_cover_size(cover_px)
        self._apply_grid_size()
        # The delegate size changed under the model, force a relayout
        self._model.layoutChanged.emit()
        self.scheduleDelayedItemsLayout()

    def _apply_grid_size(self) -> None:
        """Match the grid cell to the delegate tile size.

        :returns: None.
        """
        tile = self._delegate.tile_size()
        self.setGridSize(QSize(tile.width() + self.spacing(), tile.height() + self.spacing()))

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Drop queued covers on resize, the visible set changes.

        :param event: Qt resize event.
        :returns: None.
        """
        super().resizeEvent(event)
        self._loader.drop_pending()

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        """Drop queued covers while scrolling so the loader chases the viewport.

        :param dx: Horizontal scroll delta.
        :param dy: Vertical scroll delta.
        :returns: None.
        """
        super().scrollContentsBy(dx, dy)
        if dy:
            self._loader.drop_pending()

    @QtCore.pyqtSlot(str, int)
    def _on_cover_ready(self, cover_hash: str, size: int) -> None:
        """Repaint the tiles whose cover just finished loading.

        Only the size the grid is drawing at is relevant; another size means the tile
        was resized in the meantime and will request the right one on the next paint.

        :param cover_hash: Hash of the ready cover.
        :param size: Cached size that was loaded.
        :returns: None.
        """
        if size != CoverCache.nearest_size(self._delegate.current_cover_size()):
            return
        first = self.indexAt(self.rect().topLeft())
        if not first.isValid():
            first = self._model.index(0, 0)
        # Walk the visible rows and update the matching tiles, cheaper than a full repaint
        row = first.row()
        viewport_rect = self.viewport().rect()
        while row < self._model.rowCount():
            index = self._model.index(row, 0)
            item_rect = self.visualRect(index)
            if item_rect.top() > viewport_rect.bottom():
                break
            if index.data(AlbumRoles.COVER_HASH) == cover_hash:
                self.viewport().update(item_rect)
            row += 1

    def _on_activated(self, index: QModelIndex) -> None:
        """Emit the album id of an activated tile.

        :param index: Activated cell.
        :returns: None.
        """
        album_id = index.data(AlbumRoles.ALBUM_ID)
        if album_id is not None:
            self.albumActivated.emit(int(album_id))
