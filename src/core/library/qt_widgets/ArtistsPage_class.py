from typing import TYPE_CHECKING

from PyQt6 import QtCore
from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QSlider, QStackedLayout,
                             QVBoxLayout, QWidget)

from src.api.db.db_handler import create_session
from src.api.db import library_repo
from src.core.library.cover_cache import CoverLoader
from src.core.library.qt_widgets.ArtistGridView_class import ArtistGridView
from src.core.library.qt_widgets.CoverTileDelegate_class import CoverTileDelegate
from src.enums import ArtistSort
from src.global_styles import AppColorSchemes

if TYPE_CHECKING:
    from src.forms import MainForm

# Debounce so a search reloads once the user pauses, not on every keystroke
_SEARCH_DEBOUNCE_MS = 250

_TILE_SIZES = (CoverTileDelegate.COVER_SMALL,
               CoverTileDelegate.COVER_MEDIUM,
               CoverTileDelegate.COVER_LARGE)


class ArtistsPage(QWidget):
    """The artist grid: a wrapping grid of circular artist tiles with its own controls.

    Self-contained like the all-tracks page, it carries its own search, sort and tile
    size rather than sharing the album header, so switching views never leaves a control
    pointed at the wrong list.

    :signals: artistActivated (int) - artist id of a clicked tile
    """
    artistActivated = QtCore.pyqtSignal(int)

    def __init__(self, mf: "MainForm", cover_loader: CoverLoader, *args, **kwargs):
        """Build the page.

        :param mf: Main form.
        :param cover_loader: Cover loader shared with the rest of the library tab.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.mf = mf
        self._sort: ArtistSort = ArtistSort.NAME
        self._has_search: bool = False

        self.setObjectName("ArtistsRoot")
        self.setStyleSheet(f"""
        QWidget#ArtistsRoot {{ background-color: {AppColorSchemes.FILE_LIST_BACKGROUND}; }}
        QLabel {{ color: #222222; background-color: transparent; }}
        QLineEdit {{
            background-color: {AppColorSchemes.FILE_LIST_ITEM_BODY}; border: 0px; border-radius: 6px;
            padding: 5px 10px; color: #111111;
        }}
        QComboBox {{
            background-color: {AppColorSchemes.FILE_LIST_ITEM_BODY}; border: 0px; border-radius: 6px;
            padding: 4px 10px; color: #111111; min-width: 130px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {AppColorSchemes.FILE_LIST_ITEM_BODY}; color: #111111;
            selection-background-color: {AppColorSchemes.BUTTON_HOVER};
        }}
        QSlider::groove:horizontal {{
            height: 4px; background: {AppColorSchemes.SCROLLBAR_BACKGROUND}; border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            width: 14px; margin: -6px 0; border-radius: 7px; background: {AppColorSchemes.SCROLLBAR_BODY};
        }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # region header
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
        header.addWidget(self.search_edit, 1)
        header.addWidget(self.sort_label)
        header.addWidget(self.sort_combo)
        header.addWidget(self.size_label)
        header.addWidget(self.size_slider)
        header.addStretch(0)
        header.addWidget(self.count_label)
        root.addLayout(header)
        # endregion

        # region grid with the empty state behind it
        stack_host = QWidget(self)
        self._stack = QStackedLayout(stack_host)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self.grid = ArtistGridView(cover_loader, self)
        self.grid.artistActivated.connect(self.artistActivated)
        self.grid.set_cover_size(_TILE_SIZES[self.size_slider.value()])
        self.empty_label = QLabel(self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_font = QFont("Arima")
        empty_font.setPointSize(12)
        self.empty_label.setFont(empty_font)
        self._stack.addWidget(self.grid)
        self._stack.addWidget(self.empty_label)
        root.addWidget(stack_host, 1)
        # endregion

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(_SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self.reload)

        self._build_sort_items()
        self.retranslate_ui()

    # region i18n
    def changeEvent(self, event: QEvent) -> None:
        """Reapply the texts when the application language changes.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self._build_sort_items()
            self.retranslate_ui()
        super().changeEvent(event)

    def _build_sort_items(self) -> None:
        """Fill the sort selector, keeping the current choice.

        :returns: None.
        """
        options = [
            (ArtistSort.NAME, self.tr("Name")),
            (ArtistSort.ALBUM_COUNT, self.tr("Album count")),
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
        self.search_edit.setPlaceholderText(self.tr("Search artists"))
        self.sort_label.setText(self.tr("Sort:"))
        self.size_label.setText(self.tr("Size:"))
        self._update_count()
        self._update_empty_label()
    # endregion

    # region data
    def reload(self) -> None:
        """Reload the grid from the library for the current search and sort.

        :returns: None.
        """
        search = self.search_edit.text().strip() or None
        session = create_session()
        try:
            rows = library_repo.list_artists(session, search=search, sort=self._sort)
        finally:
            session.close()
        self.grid.model().set_rows(rows)
        self._has_search = search is not None
        self._update_count()
        self._update_empty_state()

    def _update_count(self) -> None:
        """Refresh the artist count in the header.

        :returns: None.
        """
        self.count_label.setText(self.tr("%n artist(s)", "", self.grid.model().rowCount()))

    def _update_empty_state(self) -> None:
        """Show the grid or the empty-state label depending on the result.

        :returns: None.
        """
        self._update_empty_label()
        empty = self.grid.model().rowCount() == 0
        self._stack.setCurrentWidget(self.empty_label if empty else self.grid)

    def _update_empty_label(self) -> None:
        """Set the empty-state wording for the current situation.

        :returns: None.
        """
        if self._has_search:
            self.empty_label.setText(self.tr("Nothing found"))
        else:
            self.empty_label.setText(self.tr("No artists yet.\nAdd a folder to fill the library."))
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
            self.reload()

    def _on_size_changed(self, value: int) -> None:
        """Apply a new tile size.

        :param value: Slider stop.
        :returns: None.
        """
        self.grid.set_cover_size(_TILE_SIZES[value])
    # endregion
