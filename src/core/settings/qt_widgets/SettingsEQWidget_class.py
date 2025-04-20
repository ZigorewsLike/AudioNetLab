import os
import pickle
from typing import Dict, Union, TYPE_CHECKING, Optional, List


from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QPointF, Qt, QPoint, QThread, QSize, QRect
from PyQt6.QtGui import (QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QLinearGradient, QPen, QFont,
                         QResizeEvent, QShowEvent)
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel, QPushButton, QFileDialog, QSlider, QComboBox

from src.global_constants import GENRE_DICT, EQ_SLIDER_COUNT, RESOURCE_DIR
from src.core.log_system import print_d, print_e, print_i
from src.core.qt_widgets import BaseTabWidget, EQWidget
from src.enums import EQType

if TYPE_CHECKING:
    from src.forms import MainForm


class SettingsEQWidget(QWidget):
    onPresetChanged = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.preset_combo_box = QComboBox(self)
        self.preset_combo_box.addItems(list(GENRE_DICT.values()))
        self.preset_combo_box.move(5, 5)
        self.preset_combo_box.currentIndexChanged.connect(self.on_switch_preset)

        self.eq: EQWidget = EQWidget(EQType.PRESET, self)
        self.eq.move(5, 10 + self.preset_combo_box.height())
        self.eq.slidersValueChange.connect(self.on_slider_value_changed)

        self.save_button = QPushButton("Save preset", self)
        self.save_button.clicked.connect(self.save_presets_on_file)

        self.load_button = QPushButton("Load preset", self)
        self.load_button.clicked.connect(self.load_preset_from_file)

        self.presets: Dict[int, List[float]] = {}
        self.load_preset_from_file()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.eq.adjustSize()
        
    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.eq.adjustSize()
        self.save_button.move(5, self.eq.height() + self.eq.y() + 5)
        self.load_button.move(self.save_button.width() + 10, self.eq.height() + self.eq.y() + 5)

    @pyqtSlot(int)
    def on_switch_preset(self, index: int) -> None:
        print_d(self.preset_combo_box.currentText(), index)
        gains = self.presets.get(index, [1.0] * EQ_SLIDER_COUNT)
        self.eq.set_sliders([round(gain * self.eq.accuracy) for gain in gains])

    @pyqtSlot(list)
    def on_slider_value_changed(self, gains: list) -> None:
        self.presets[self.preset_combo_box.currentIndex()] = gains

    @pyqtSlot()
    def save_presets_on_file(self) -> None:
        save_path = os.path.join(RESOURCE_DIR, 'presets.pickle')
        with open(save_path, 'wb') as f:
            pickle.dump(self.presets, f)
        self.onPresetChanged.emit(self.presets)

    @pyqtSlot()
    def load_preset_from_file(self) -> Dict[int, List[float]]:
        preset_path = os.path.join(RESOURCE_DIR, 'presets.pickle')
        try:
            if not os.path.exists(preset_path):
                raise FileExistsError
            with open(preset_path, 'rb') as f:
                presets: Dict[int, List[float]] = pickle.load(f)
                # _l = {}
                # for key, values in presets.items():
                #     _l[key] = [value / 100 for value in values]
                # self.presets = _l
                # self.save_presets_on_file()
                # return self.presets
        except (FileExistsError, Exception) as e:
            presets: Dict[int, List[float]] = {}
            for key in GENRE_DICT.keys():
                presets[key] = [self.eq.accuracy] * EQ_SLIDER_COUNT
        self.presets = presets
        self.on_switch_preset(self.preset_combo_box.currentIndex())
        return presets






