from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSlot, Qt, QEvent
from PyQt6.QtGui import QFont, QResizeEvent, QPaintEvent, QPainter, QColor, QPen
from PyQt6.QtWidgets import QLabel, QFrame, QTreeWidget, QTreeWidgetItem

from .SettingsAudioWidget_class import SettingsAudioWidget
from .SettingsEQWidget_class import SettingsEQWidget
from .SettingsInterfaceWidget_class import SettingsInterfaceWidget
from .SettingsLibraryWidget_class import SettingsLibraryWidget

if TYPE_CHECKING:
    from src.forms import MainForm

from src.core.qt_widgets import BaseTabWidget
from src.global_constants import VERSION_FULL, APP_COPYRIGHT


class SettingsFrame(QFrame):
    """Settings tab: a section tree on the left and the matching page on the right."""

    def __init__(self, mf):
        """Build the section tree and the settings pages.

        :param mf: Main form reference.
        :returns: None.
        """
        super().__init__()

        self.bottom_panel_height: int = 0
        self.top_panel_height: int = 40
        self.mf: MainForm = mf
        self.tree_widget_width: int = 160

        self.form_title = QLabel("", self)
        self.form_title.move(10, 10)
        self.form_title.setFont(QFont('Arial', 12))

        self.tab_widget = BaseTabWidget(self)
        self.tab_widget.margin = 0
        self.tab_widget.move(self.tree_widget_width + 10, self.top_panel_height)

        self.tree_widget = QTreeWidget(self)
        self.tree_widget.header().setVisible(False)
        self.tree_widget.move(0, self.top_panel_height)
        self.tree_widget.itemClicked.connect(self.on_item_click)

        font_item = QFont('Arial', 10)

        self.audio_settings = SettingsAudioWidget(self.mf)
        self.eq_settings = SettingsEQWidget()
        self.interface_settings = SettingsInterfaceWidget(self.mf)
        self.library_settings = SettingsLibraryWidget(self.mf)

        # The tree item order must match the order the pages are added in
        self.audio_tree_item = QTreeWidgetItem([""])
        self.audio_tree_item.setFont(0, font_item)
        self.tree_widget.insertTopLevelItem(0, self.audio_tree_item)
        self.tab_widget.add_tab(self.audio_settings, "")

        self.eq_tree_item = QTreeWidgetItem([""])
        self.eq_tree_item.setFont(0, font_item)
        self.tree_widget.insertTopLevelItem(1, self.eq_tree_item)
        self.tab_widget.add_tab(self.eq_settings, "")

        self.interface_tree_item = QTreeWidgetItem([""])
        self.interface_tree_item.setFont(0, font_item)
        self.tree_widget.insertTopLevelItem(2, self.interface_tree_item)
        self.tab_widget.add_tab(self.interface_settings, "")

        self.library_tree_item = QTreeWidgetItem([""])
        self.library_tree_item.setFont(0, font_item)
        self.tree_widget.insertTopLevelItem(3, self.library_tree_item)
        self.tab_widget.add_tab(self.library_settings, "")

        self.tree_widget.expandAll()
        self.tree_widget.setCurrentItem(self.tree_widget.topLevelItem(0))

        self.app_version_label = QLabel(f"{VERSION_FULL}", self)
        self.app_version_label.adjustSize()

        self.app_copyright_label = QLabel(APP_COPYRIGHT, self)
        self.app_copyright_label.setWordWrap(True)
        self.app_copyright_label.setMaximumWidth(self.tree_widget_width)
        self.app_copyright_label.adjustSize()

        self.retranslate_ui()

    @pyqtSlot(QTreeWidgetItem, int)
    def on_item_click(self, item: QTreeWidgetItem, column: int):
        """Show the page that belongs to the clicked tree item.

        :param item: Clicked tree item.
        :param column: Clicked column, unused.
        :returns: None.
        """
        index = self.tree_widget.indexOfTopLevelItem(item)
        self.tab_widget.active_tab(index)

    def changeEvent(self, event: QEvent) -> None:
        """Reapply the texts when the application language changes.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self) -> None:
        """Apply the current translation to the title and the section names.

        :returns: None.
        """
        self.form_title.setText(self.tr("Settings"))
        self.form_title.adjustSize()
        self.audio_tree_item.setText(0, self.tr("Audio settings"))
        self.eq_tree_item.setText(0, self.tr("Equalizer presets"))
        self.interface_tree_item.setText(0, self.tr("Interface"))
        self.library_tree_item.setText(0, self.tr("Library"))

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Lay out the tree and the pages on resize.

        :param event: Qt resize event.
        :returns: None.
        """
        super().resizeEvent(event)
        self.recalc_sizes()

    def recalc_sizes(self):
        """Fit the tree, the pages and the version label to the current size.

        :returns: None.
        """
        self.app_copyright_label.move(10, self.height() - self.app_copyright_label.height() - 2)
        self.app_version_label.move(10, self.app_copyright_label.y() - self.app_version_label.height() - 2)
        self.tab_widget.content_width = self.width() - self.tree_widget_width - 20
        self.tab_widget.resize(self.tab_widget.content_width, self.height() - self.bottom_panel_height)
        self.tree_widget.resize(self.tree_widget_width,
                                self.height() - self.bottom_panel_height - self.top_panel_height)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the separator between the tree and the pages.

        :param event: Qt paint event.
        :returns: None.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setPen(QPen(QColor("#8a8a8a"), 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.drawLine(self.tree_widget_width - 1, 0, self.tree_widget_width - 1, self.height() - 1)