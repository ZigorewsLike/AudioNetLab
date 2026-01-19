from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSlot, Qt
from PyQt6.QtGui import QFont, QResizeEvent, QPaintEvent, QPainter, QColor, QPen
from PyQt6.QtWidgets import QLabel, QFrame, QTreeWidget, \
    QTreeWidgetItem, QPushButton

from .SettingsAudioWidget_class import SettingsAudioWidget
from .SettingsEQWidget_class import SettingsEQWidget

if TYPE_CHECKING:
    from src.forms import MainForm

from src.core.qt_widgets import BaseTabWidget
from src.global_constants import VERSION
from src.global_strings import String
from .help_widgets import QLabelHelp, QSpinBoxHelp, QCheckBoxHelp, QLineEditHelp
from .SettingsSection_class import SettingsSection, SettingsSubSection


class SettingsFrame(QFrame):

    def __init__(self, mf, lang_string: String = String()):
        super().__init__()

        self.bottom_panel_height: int = 0
        self.top_panel_height: int = 40
        self.strings: String = lang_string
        self.mf: MainForm = mf
        self.tree_widget_width: int = 160

        # region Новый UI
        self.form_title = QLabel("Настройки", self)
        self.form_title.move(10, 10)
        self.form_title.setFont(QFont('Arial', 12))
        self.form_title.adjustSize()

        self.tab_widget = BaseTabWidget(self)
        self.tab_widget.margin = 0
        self.tab_widget.move(self.tree_widget_width + 10, self.top_panel_height)

        self.tree_widget = QTreeWidget(self)
        self.tree_widget.setHeaderLabel('Settings')
        self.tree_widget.header().setVisible(False)
        self.tree_widget.move(0, self.top_panel_height)
        self.tree_widget.itemClicked.connect(self.on_item_click)

        font_item = QFont('Arial', 10)

        self.audio_settings = SettingsAudioWidget(self.mf)
        self.eq_settings = SettingsEQWidget()

        # region Основные настройки
        self.common_tree_item = QTreeWidgetItem(["Настройки аудио"])
        self.common_tree_item.setFont(0, font_item)
        self.tree_widget.insertTopLevelItem(0, self.common_tree_item)
        self.tab_widget.add_tab(self.audio_settings, "Настройки аудио")

        self.interface_tree_item = QTreeWidgetItem(["Пресеты эквалайзера"])
        self.interface_tree_item.setFont(0, font_item)
        self.tree_widget.insertTopLevelItem(1, self.interface_tree_item)
        self.tab_widget.add_tab(self.eq_settings, "Пресеты эквалайзера")
        # endregion

        self.tree_widget.expandAll()
        self.tree_widget.setCurrentItem(self.tree_widget.topLevelItem(0))
        # endregion

        self.app_version_label = QLabel(f"{VERSION}", self)
        self.app_version_label.adjustSize()

    @pyqtSlot(QTreeWidgetItem, int)
    def on_item_click(self, item: QTreeWidgetItem, column: int):
        index = self.tree_widget.indexOfTopLevelItem(item)
        self.tab_widget.active_tab(index)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.recalc_sizes()

    def recalc_sizes(self):
        self.app_version_label.move(10, self.height() - self.app_version_label.height() - 10)
        self.tab_widget.content_width = self.width() - self.tree_widget_width - 20
        self.tab_widget.resize(self.tab_widget.content_width, self.height() - self.bottom_panel_height)
        self.tree_widget.resize(self.tree_widget_width,
                                      self.height() - self.bottom_panel_height - self.top_panel_height)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setPen(QPen(QColor("#8a8a8a"), 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        # painter.drawLine(0, 0, 2, 0)
        painter.drawLine(self.tree_widget_width - 1, 0, self.tree_widget_width - 1, self.height()-1)
        # painter.drawLine(0, self.height()-1, 2, self.height()-1)



