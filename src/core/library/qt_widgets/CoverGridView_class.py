from PyQt6 import QtCore
from PyQt6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import QAbstractItemView, QListView

from src.core.library.cover_cache import CoverLoader
from src.core.library.qt_widgets.CoverTileDelegate_class import CoverTileDelegate
from src.global_styles import AppColorSchemes, DEFAULT_SCROLLBAR_STYLE


class CoverGridView(QListView):
    """Icon-mode grid of cover tiles, shared by the album grid and the artist grid.

    The heavy lifting is left to QListView: it paints only the visible tiles, so the
    grid stays smooth on a library of thousands. uniformItemSizes lets it skip measuring
    every row, batched layout keeps a resize from freezing, and the covers of tiles that
    scrolled past are dropped from the loader queue so a fast scroll never backs up behind
    covers nobody is looking at any more. A subclass supplies the model, the tile delegate
    and the roles carrying the item id and the cover hash.

    :signals: itemActivated (int) - id of a clicked tile
    """
    itemActivated = QtCore.pyqtSignal(int)

    def __init__(self, cover_loader: CoverLoader, model: QAbstractListModel,
                 delegate: CoverTileDelegate, id_role: int, cover_hash_role: int,
                 *args, **kwargs):
        """Build the grid.

        :param cover_loader: Loader shared with the delegate.
        :param model: List model holding the tile rows.
        :param delegate: Tile delegate that paints the covers.
        :param id_role: Item data role carrying the item id.
        :param cover_hash_role: Item data role carrying the cover hash.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self._loader = cover_loader
        self._id_role = id_role
        self._cover_hash_role = cover_hash_role
        self._open_on_double_click = False

        self._model = model
        self._model.setParent(self)
        self.setModel(self._model)

        self._delegate = delegate
        self._delegate.setParent(self)
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
        # Both are wired; the flag decides which gesture opens, so it can change live
        self.clicked.connect(self._on_clicked)
        self.doubleClicked.connect(self._on_double_clicked)

    def model(self) -> QAbstractListModel:
        """The typed model backing the grid.

        :returns: QAbstractListModel - The model.
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
        if size != self._delegate.cover_size_for_repaint():
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
            if index.data(self._cover_hash_role) == cover_hash:
                self.viewport().update(item_rect)
            row += 1

    def set_open_on_double_click(self, enabled: bool) -> None:
        """Choose whether a tile opens on a double click instead of a single one.

        :param enabled: True to open on double click.
        :returns: None.
        """
        self._open_on_double_click = enabled

    def _on_clicked(self, index: QModelIndex) -> None:
        """Open on a single click when the double-click mode is off.

        :param index: Clicked cell.
        :returns: None.
        """
        if not self._open_on_double_click:
            self._on_activated(index)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        """Open on a double click when the double-click mode is on.

        :param index: Double-clicked cell.
        :returns: None.
        """
        if self._open_on_double_click:
            self._on_activated(index)

    def _on_activated(self, index: QModelIndex) -> None:
        """Emit the id of an opened tile.

        :param index: Opened cell.
        :returns: None.
        """
        item_id = index.data(self._id_role)
        if item_id is not None:
            self.itemActivated.emit(int(item_id))
