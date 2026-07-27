from typing import TYPE_CHECKING

from PyQt6 import QtCore
from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QSlider, QStackedLayout, QStackedWidget, QVBoxLayout, QWidget)

from src.api.db.db_handler import create_session
from src.api.db import library_repo
from src.core.file_system.qt_widgets import LastFileList
from src.core.library.cover_cache import CoverLoader
from src.core.library.qt_widgets.AlbumGridView_class import AlbumGridView
from src.core.library.qt_widgets.AlbumPage_class import AlbumPage
from src.core.library.qt_widgets.AlbumTileDelegate_class import AlbumTileDelegate
from src.enums import AlbumSort
from src.global_styles import AppColorSchemes

if TYPE_CHECKING:
    from src.forms import MainForm

# Debounce so a search reloads once the user pauses, not on every keystroke
_SEARCH_DEBOUNCE_MS = 250

# Slider stop to cover edge, the middle stop is the default
_TILE_SIZES = (AlbumTileDelegate.COVER_SMALL,
               AlbumTileDelegate.COVER_MEDIUM,
               AlbumTileDelegate.COVER_LARGE)

# Pages of the view switch
_PAGE_ALBUMS = 0
_PAGE_TRACKS = 1
_PAGE_ALBUM_DETAIL = 2  # The detail page of one album, reached by clicking a tile


class LibraryTabWidget(QWidget):
    """The library tab, the single home of everything that was imported.

    Holds two views the user switches between: the album cover grid and the flat
    track list that used to be the home page. A top bar carries the view switch and
    the open and add entry points; the album controls (search, sort, tile size) show
    only on the album view. The whole tab reloads whenever a scan changes the library.

    :signals: albumActivated (int) - album id of an activated tile
    """
    albumActivated = QtCore.pyqtSignal(int)

    def __init__(self, mf: "MainForm", *args, **kwargs):
        """Build the tab.

        :param mf: Main form, the track list and the entry buttons reach for it.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.mf = mf
        self.setAutoFillBackground(True)

        self._cover_loader = CoverLoader(max_workers=2)
        self._sort: AlbumSort = AlbumSort.ARTIST
        self._has_search: bool = False

        self.setObjectName("LibraryRoot")
        self.setStyleSheet(self._build_style())

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        root.addLayout(self._build_top_bar())
        root.addLayout(self._build_album_header())

        # region pages
        self.pages = QStackedWidget(self)

        # Album page: the grid, with an empty-state label stacked behind it
        albums_page = QWidget(self)
        albums_layout = QStackedLayout(albums_page)
        albums_layout.setContentsMargins(0, 0, 0, 0)
        self.grid = AlbumGridView(self._cover_loader, self)
        # A tile opens the album page; playing is started from there. albumActivated is
        # still forwarded for anything that wants the raw activation.
        self.grid.albumActivated.connect(self.open_album)
        self.grid.albumActivated.connect(self.albumActivated)
        self.grid.set_cover_size(_TILE_SIZES[self.size_slider.value()])
        self.empty_label = QLabel(self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_font = QFont("Arima")
        empty_font.setPointSize(12)
        self.empty_label.setFont(empty_font)
        albums_layout.addWidget(self.grid)
        albums_layout.addWidget(self.empty_label)
        self._albums_layout = albums_layout

        # Track page: the recent-track list, moved here from the old home page
        self.tracks_list = LastFileList(self.width(), self.mf, self)

        # Album detail page, shown when a tile is opened
        self.album_page = AlbumPage(self.mf, self)
        self.album_page.backRequested.connect(self._on_album_back)

        self.pages.addWidget(albums_page)          # _PAGE_ALBUMS
        self.pages.addWidget(self.tracks_list)     # _PAGE_TRACKS
        self.pages.addWidget(self.album_page)      # _PAGE_ALBUM_DETAIL
        root.addWidget(self.pages, 1)
        # endregion

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(_SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self.reload_albums)

        self._build_sort_items()
        self.retranslate_ui()
        self._show_page(_PAGE_ALBUMS)
        self.reload_albums()

    # region build
    def _build_style(self) -> str:
        """The stylesheet of the tab.

        :returns: str - Qt stylesheet.
        """
        body = AppColorSchemes.FILE_LIST_ITEM_BODY
        return f"""
        QWidget#LibraryRoot {{
            background-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
        }}
        QLabel {{ color: #222222; background-color: transparent; }}
        QLineEdit {{
            background-color: {body}; border: 0px; border-radius: 6px;
            padding: 5px 10px; color: #111111;
        }}
        QComboBox {{
            background-color: {body}; border: 0px; border-radius: 6px;
            padding: 4px 10px; color: #111111; min-width: 130px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {body}; color: #111111;
            selection-background-color: {AppColorSchemes.BUTTON_HOVER};
        }}
        QSlider::groove:horizontal {{
            height: 4px; background: {AppColorSchemes.SCROLLBAR_BACKGROUND}; border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            width: 14px; margin: -6px 0; border-radius: 7px; background: {AppColorSchemes.SCROLLBAR_BODY};
        }}
        QPushButton {{
            background-color: {body}; border: 0px; border-radius: 6px;
            padding: 5px 14px; color: #111111;
        }}
        QPushButton:hover {{ background-color: {AppColorSchemes.BUTTON_HOVER}; }}
        QPushButton:checked {{ background-color: #704D93; color: white; }}
        """

    def _build_top_bar(self) -> QHBoxLayout:
        """Build the view switch and the open and add buttons.

        :returns: QHBoxLayout - The top bar.
        """
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.button_albums = QPushButton(self)
        self.button_albums.setCheckable(True)
        self.button_albums.setChecked(True)
        self.button_tracks = QPushButton(self)
        self.button_tracks.setCheckable(True)
        self.nav_group.addButton(self.button_albums, _PAGE_ALBUMS)
        self.nav_group.addButton(self.button_tracks, _PAGE_TRACKS)
        self.nav_group.idClicked.connect(self._show_page)

        self.button_open = QPushButton(self)
        self.button_open.clicked.connect(lambda: self.mf.add_file_dialog())
        self.button_add_folder = QPushButton(self)
        self.button_add_folder.clicked.connect(lambda: self.mf.add_folder_dialog())

        bar.addWidget(self.button_albums)
        bar.addWidget(self.button_tracks)
        bar.addStretch(1)
        bar.addWidget(self.button_open)
        bar.addWidget(self.button_add_folder)
        return bar

    def _build_album_header(self) -> QHBoxLayout:
        """Build the album controls: search, sort and tile size.

        :returns: QHBoxLayout - The album header.
        """
        header = QHBoxLayout()
        header.setSpacing(10)

        self.search_edit = QLineEdit(self)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)

        self.sort_label = QLabel(self)
        self.sort_combo = QComboBox(self)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)

        self.size_label = QLabel(self)
        self.size_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.size_slider.setMinimum(0)
        self.size_slider.setMaximum(len(_TILE_SIZES) - 1)
        self.size_slider.setValue(1)
        self.size_slider.setFixedWidth(90)
        self.size_slider.setPageStep(1)
        self.size_slider.valueChanged.connect(self._on_size_changed)

        self.count_label = QLabel(self)
        count_font = QFont("Arima")
        count_font.setPointSize(9)
        self.count_label.setFont(count_font)

        # Kept as widgets so the header can be shown and hidden as a whole
        self._album_header_widgets = [self.search_edit, self.sort_label, self.sort_combo,
                                      self.size_label, self.size_slider, self.count_label]

        header.addWidget(self.search_edit, 1)
        header.addWidget(self.sort_label)
        header.addWidget(self.sort_combo)
        header.addWidget(self.size_label)
        header.addWidget(self.size_slider)
        header.addStretch(0)
        header.addWidget(self.count_label)
        return header
    # endregion

    # region i18n
    def changeEvent(self, event: QEvent) -> None:
        """Reapply the texts when the application language changes.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _build_sort_items(self) -> None:
        """Fill the sort selector, keeping the current choice.

        :returns: None.
        """
        options = [
            (AlbumSort.ARTIST, self.tr("Artist")),
            (AlbumSort.TITLE, self.tr("Title")),
            (AlbumSort.YEAR, self.tr("Year")),
            (AlbumSort.DATE_ADDED, self.tr("Recently added")),
        ]
        self.sort_combo.blockSignals(True)
        self.sort_combo.clear()
        for value, label in options:
            self.sort_combo.addItem(label, value)
        index = self.sort_combo.findData(self._sort)
        self.sort_combo.setCurrentIndex(max(0, index))
        self.sort_combo.blockSignals(False)

    def retranslate_ui(self) -> None:
        """Apply the current translation to the controls and the empty state.

        :returns: None.
        """
        self.button_albums.setText(self.tr("Albums"))
        self.button_tracks.setText(self.tr("Recent"))
        self.button_open.setText(self.tr("Open file"))
        self.button_add_folder.setText(self.tr("Add folder"))
        self.search_edit.setPlaceholderText(self.tr("Search albums and artists"))
        self.sort_label.setText(self.tr("Sort:"))
        self.size_label.setText(self.tr("Size:"))
        self._build_sort_items()
        self._update_count()
        self._update_empty_label()
    # endregion

    # region pages
    def _show_page(self, page: int) -> None:
        """Switch between the album grid, the track list and the album detail page.

        The nav buttons only cover the grid and the list; opening an album from the grid
        goes to the detail page but keeps the Albums button lit, since it is still part
        of the albums view.

        :param page: One of the page constants.
        :returns: None.
        """
        self.pages.setCurrentIndex(page)
        # The album controls belong to the grid only
        for widget in self._album_header_widgets:
            widget.setVisible(page == _PAGE_ALBUMS)
        if page == _PAGE_ALBUMS:
            self._cover_loader.drop_pending()

    @QtCore.pyqtSlot(int)
    def open_album(self, album_id: int) -> None:
        """Show the detail page of an album.

        :param album_id: Album id.
        :returns: None.
        """
        self.album_page.load(album_id)
        self.button_albums.setChecked(True)
        self._show_page(_PAGE_ALBUM_DETAIL)

    def _on_album_back(self) -> None:
        """Return from the album detail page to the grid.

        :returns: None.
        """
        self._show_page(_PAGE_ALBUMS)
    # endregion

    # region data
    def reload_albums(self) -> None:
        """Reload the album grid from the library for the current search and sort.

        :returns: None.
        """
        search = self.search_edit.text().strip() or None
        session = create_session()
        try:
            rows = library_repo.list_albums(session, search=search, sort=self._sort)
        finally:
            session.close()
        self.grid.model().set_rows(rows)
        self._cover_loader.drop_pending()
        self._has_search = search is not None
        self._update_count()
        self._update_empty_state()

    def reload(self) -> None:
        """Reload both views after the library changed.

        :returns: None.
        """
        self.reload_albums()
        self.tracks_list.update_file_list()

    def _update_count(self) -> None:
        """Refresh the album count in the header.

        :returns: None.
        """
        count = self.grid.model().rowCount()
        self.count_label.setText(self.tr("%n album(s)", "", count))

    def _update_empty_state(self) -> None:
        """Show the grid or the empty-state label depending on the result.

        :returns: None.
        """
        self._update_empty_label()
        empty = self.grid.model().rowCount() == 0
        self._albums_layout.setCurrentWidget(self.empty_label if empty else self.grid)

    def _update_empty_label(self) -> None:
        """Set the empty-state wording for the current situation.

        :returns: None.
        """
        if self._has_search:
            self.empty_label.setText(self.tr("Nothing found"))
        else:
            self.empty_label.setText(self.tr("The library is empty.\nAdd a folder to fill it."))
    # endregion

    # region controls
    def _on_search_changed(self, _text: str) -> None:
        """Restart the debounce timer on every keystroke.

        :param _text: Current text, unused.
        :returns: None.
        """
        self._search_timer.start()

    def _on_sort_changed(self, _index: int) -> None:
        """Apply a new sort and reload.

        :param _index: New combo index, unused, the value is read from the data.
        :returns: None.
        """
        value = self.sort_combo.currentData()
        if value is not None:
            self._sort = value
            self.reload_albums()

    def _on_size_changed(self, value: int) -> None:
        """Apply a new tile size.

        :param value: Slider stop.
        :returns: None.
        """
        self.grid.set_cover_size(_TILE_SIZES[value])
    # endregion

    def shutdown(self) -> None:
        """Stop the cover loader threads, called when the window closes.

        :returns: None.
        """
        self._cover_loader.shutdown()
