import os
import pickle
from typing import Dict, TYPE_CHECKING, List

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent
from PyQt6.QtGui import QResizeEvent, QShowEvent
from PyQt6.QtWidgets import QWidget, QPushButton, QComboBox

from src.global_constants import GENRE_DICT, EQ_SLIDER_COUNT, RESOURCE_DIR
from src.core.qt_widgets import EQWidget
from src.enums import EQType

if TYPE_CHECKING:
    from src.forms import MainForm


class SettingsEQWidget(QWidget):
    """Settings tab where an EQ preset is edited for every genre.

    Presets are stored in res/presets.pickle as {genre index: [band gains]} and are
    used by the auto EQ mode of the genre classifier.

    :signals: onPresetChanged (dict) - full preset map after a save
    """
    onPresetChanged = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        """Build the genre selector, the equalizer and the save/load buttons.

        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.preset_combo_box = QComboBox(self)
        self.preset_combo_box.addItems(list(GENRE_DICT.values()))
        self.preset_combo_box.move(5, 5)
        self.preset_combo_box.currentIndexChanged.connect(self.on_switch_preset)

        self.eq: EQWidget = EQWidget(EQType.PRESET, self)
        self.eq.move(5, 10 + self.preset_combo_box.height())
        self.eq.slidersValueChange.connect(self.on_slider_value_changed)

        self.save_button = QPushButton("", self)
        self.save_button.clicked.connect(self.save_presets_on_file)

        self.load_button = QPushButton("", self)
        self.load_button.clicked.connect(self.load_preset_from_file)

        self.presets: Dict[int, List[float]] = {}
        self.load_preset_from_file()
        self.retranslate_ui()

    def changeEvent(self, event: QEvent) -> None:
        """Reapply the texts when the application language changes.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self) -> None:
        """Apply the current translation to the buttons of this page.

        :returns: None.
        """
        self.save_button.setText(self.tr("Save preset"))
        self.save_button.adjustSize()
        self.load_button.setText(self.tr("Load preset"))
        self.load_button.adjustSize()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Fit the equalizer on resize.

        :param event: Qt resize event.
        :returns: None.
        """
        super().resizeEvent(event)
        self.eq.adjustSize()

    def showEvent(self, event: QShowEvent) -> None:
        """Place the buttons under the equalizer once its size is known.

        :param event: Qt show event.
        :returns: None.
        """
        super().showEvent(event)
        self.eq.adjustSize()
        self.save_button.move(5, self.eq.height() + self.eq.y() + 5)
        self.load_button.move(self.save_button.width() + 10, self.eq.height() + self.eq.y() + 5)

    @pyqtSlot(int)
    def on_switch_preset(self, index: int) -> None:
        """Load the preset of the selected genre into the sliders.

        :param index: Genre index from the combo box.
        :returns: None.
        """
        gains = self.presets.get(index, [1.0] * EQ_SLIDER_COUNT)
        self.eq.set_sliders([round(gain * self.eq.accuracy) for gain in gains])

    @pyqtSlot(list)
    def on_slider_value_changed(self, gains: list) -> None:
        """Store the edited gains in the preset of the selected genre.

        :param gains: Linear gain per band.
        :returns: None.
        """
        self.presets[self.preset_combo_box.currentIndex()] = gains

    @pyqtSlot()
    def save_presets_on_file(self) -> None:
        """Write every preset to disk and notify the listeners.

        :returns: None.
        """
        save_path = os.path.join(RESOURCE_DIR, 'presets.pickle')
        with open(save_path, 'wb') as f:
            pickle.dump(self.presets, f)
        self.onPresetChanged.emit(self.presets)

    @pyqtSlot()
    def load_preset_from_file(self) -> Dict[int, List[float]]:
        """Read the presets from disk, falling back to flat ones.

        :returns: Dict[int, List[float]] - Band gains per genre index.
        """
        preset_path = os.path.join(RESOURCE_DIR, 'presets.pickle')
        try:
            if not os.path.exists(preset_path):
                raise FileExistsError
            with open(preset_path, 'rb') as f:
                presets: Dict[int, List[float]] = pickle.load(f)
        except (FileExistsError, Exception) as e:
            presets: Dict[int, List[float]] = {}
            for key in GENRE_DICT.keys():
                presets[key] = [self.eq.accuracy] * EQ_SLIDER_COUNT
        self.presets = presets
        self.on_switch_preset(self.preset_combo_box.currentIndex())
        return presets