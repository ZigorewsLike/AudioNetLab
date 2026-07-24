from typing import Union, TYPE_CHECKING, Optional, List

import numpy as np
from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, Qt, QSize, QRect
from PyQt6.QtGui import QPaintEvent, QPainter, QColor, QPen, QIcon
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QSlider, QFrame

from src.enums import EQType
from src.global_constants import EQ_SLIDER_COUNT, RESOURCE_ICON_DIR
from .ScrollButtonWidget_class import ScrollButtonWidget

if TYPE_CHECKING:
    pass


class EQWidgetSliderFrame(QFrame):
    """Frame behind the EQ sliders that draws the 0 dB line and the boost/cut guides."""

    def __init__(self, *args, **kwargs) -> None:
        """Create the frame.

        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.slider_padding: int = 26
        self.color: str = "#4C4C4C"
        self.setAutoFillBackground(True)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the centre line and the two dashed guide lines.

        :param event: Qt paint event.
        :returns: None.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(QColor(self.color), 1.0, Qt.PenStyle.SolidLine))
        painter.drawLine(self.slider_padding, 85, self.width() - self.slider_padding, 85)
        painter.setPen(QPen(QColor(self.color), 1.0, Qt.PenStyle.DashLine))
        painter.drawLine(self.slider_padding, 53, self.width() - self.slider_padding, 53)
        painter.drawLine(self.slider_padding, 108, self.width() - self.slider_padding, 108)


class EQWidget(QWidget):
    """Equalizer with EQ_SLIDER_COUNT bands.

    Two flavours are used: EQType.ACTIVE affects playback and can follow the genre
    automatically, EQType.PRESET only edits a stored preset.

    :signals: autoEQSwitched (bool), activeSwitched (bool), slidersValueChange (list)
    """
    autoEQSwitched = QtCore.pyqtSignal(bool)
    activeSwitched = QtCore.pyqtSignal(bool)
    slidersValueChange = QtCore.pyqtSignal(list)

    def __init__(self, eq_type: EQType, *args, **kwargs):
        """Build the sliders, the frequency labels and the side buttons.

        :param eq_type: Widget flavour, ACTIVE adds the playback control buttons.
        :returns: None.
        """
        super().__init__(*args, **kwargs)

        self.slider_count: int = EQ_SLIDER_COUNT
        self.slider_padding: int = 26
        self.button_padding: int = 20
        self.slider_container: List[QSlider] = []
        self.label_container: List[QLabel] = []
        self.slider_gains: List[int] = [0 for _ in range(self.slider_count)]
        self.eq_type: EQType = eq_type
        self.accuracy: int = 1000  # Slider units per gain of 1.0
        self.interpolation_step: int = 10

        self.active_fx: bool = True
        self.auto_eq: bool = False
        self.dark_theme: bool = True

        self.slider_frame = EQWidgetSliderFrame(self)
        self.slider_frame.move(self.button_padding, 0)

        # Two interleaved octave series give a denser grid than a single one
        frequencies = [22_000 // 2 ** x for x in range(self.slider_count // 2)]
        frequencies += [16_000 // 2 ** x for x in range(self.slider_count // 2)]
        frequencies.sort()
        self.bands = list(zip(frequencies[:-1], frequencies[1:]))

        transparent_style = """
        QSlider::handle:vertical{
            background-color: transparent;
        }
        """

        for slider_index in range(self.slider_count):
            # Sliders
            vert_slider = QSlider(self.slider_frame)
            vert_slider.setObjectName("verticalSlider")
            vert_slider.setGeometry(QRect(self.slider_padding + self.slider_padding * slider_index,
                                          20, 22, 130))
            vert_slider.setRange(0, self.accuracy * 2)
            vert_slider.setValue(self.accuracy)  # Middle position means gain 1.0
            vert_slider.setOrientation(Qt.Orientation.Vertical)
            vert_slider.valueChanged.connect(self.on_slider_value_changed)
            vert_slider.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.slider_container.append(vert_slider)
            # Labels
            freq = frequencies[slider_index]
            freq_text = f"{freq}"
            if freq > 1000:
                freq = round(freq / 1000, 1)
                freq_text = f"{freq}k"
            label = QLabel(freq_text, self.slider_frame)
            # Odd labels go below the sliders so the captions do not overlap
            label.setGeometry(int(self.slider_padding * slider_index + self.slider_padding / 2),
                              5 if slider_index % 2 == 0 else vert_slider.height() + vert_slider.y() + 5,
                              self.slider_padding + vert_slider.width(), 10)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.label_container.append(label)
        self.slider_frame.adjustSize()

        self.reset_button = QPushButton("", self)
        self.reset_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}restart_alt_eq.png"))
        self.reset_button.setIconSize(QSize(26, 26))
        self.reset_button.resize(28, 28)
        self.reset_button.move(5, 5)
        self.reset_button.clicked.connect(self.reset_eq)

        if eq_type is EQType.ACTIVE:
            self.active_button = QPushButton("", self)
            self.active_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}graphic_eq_enabled.png"))
            self.active_button.setIconSize(QSize(26, 26))
            self.active_button.resize(28, 28)
            self.active_button.move(5, self.reset_button.y() + self.reset_button.height() + 10)
            self.active_button.clicked.connect(self.switch_active_eq)

            self.auto_eq_button = QPushButton("", self)
            self.auto_eq_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}aq.png"))
            self.auto_eq_button.setIconSize(QSize(26, 26))
            self.auto_eq_button.resize(28, 28)
            self.auto_eq_button.move(5, self.active_button.y() + self.active_button.height() + 10)
            self.auto_eq_button.clicked.connect(self.switch_auto_eq)

            self.interpolation_button = ScrollButtonWidget("", self)
            self.interpolation_button.resize(28, 28)
            self.interpolation_button.set_range(2, 20)
            self.interpolation_button.set_value(10)
            self.interpolation_button.move(5, self.auto_eq_button.y() + self.auto_eq_button.height() + 10)
            self.interpolation_button.valueChanged.connect(self.set_interpolation)

    @pyqtSlot(int)
    def on_slider_value_changed(self, value: int) -> None:
        """Collect the slider values and publish them as linear gains.

        :param value: Value of the slider that changed, unused.
        :returns: None.
        """
        self.slider_gains = [slider.value() / self.accuracy for slider in self.slider_container]
        self.slidersValueChange.emit(self.slider_gains)

    def set_enabled_eq(self, enabled: Optional[bool] = None) -> None:
        """Enable or disable manual editing of the sliders.

        :param enabled: Target state, None inverts the current one.
        :returns: None.
        """
        if enabled is None:
            enabled = not self.slider_frame.isEnabled()
        self.slider_frame.setEnabled(enabled)

    @pyqtSlot()
    def switch_active_eq(self) -> None:
        """Toggle the equalizer effect on playback.

        :returns: None.
        """
        self.active_fx = not self.active_fx
        if self.active_fx:
            self.active_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}graphic_eq_enabled.png"))
        else:
            self.active_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}graphic_eq_disable.png"))
        self.activeSwitched.emit(self.active_fx)

    @pyqtSlot()
    def switch_auto_eq(self) -> None:
        """Toggle the automatic mode where the sliders follow the detected genre.

        :returns: None.
        """
        self.auto_eq = not self.auto_eq
        if self.auto_eq:
            self.auto_eq_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}aq_on.png"))
        else:
            self.auto_eq_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}aq.png"))
        self.set_enabled_eq(not self.auto_eq)  # Manual editing is locked while auto EQ drives the sliders
        self.reset_button.setEnabled(not self.auto_eq)
        self.autoEQSwitched.emit(self.auto_eq)

    @pyqtSlot()
    def reset_eq(self) -> None:
        """Return every band to a flat gain of 1.0.

        :returns: None.
        """
        if self.auto_eq:
            return
        for slider in self.slider_container:
            slider.setValue(self.accuracy)

    @pyqtSlot(int)
    def set_interpolation(self, value: int) -> None:
        """Set how many steps a slider takes to reach a new preset value.

        :param value: Number of interpolation steps, larger means smoother.
        :returns: None.
        """
        self.interpolation_step = value

    def set_sliders(self, gains: Union[List[int], np.ndarray], interpolation: bool = False) -> None:
        """Apply gain values to the sliders.

        :param gains: Slider values already scaled by accuracy.
        :param interpolation: True moves the sliders towards the target by one step instead of jumping.
        :returns: None.
        """
        for index, gain in enumerate(gains):
            slider = self.slider_container[index]
            if interpolation:
                if abs(gain - slider.value()) < self.interpolation_step:
                    slider.setValue(gain)  # Close enough, snap to the target
                else:
                    slider.setValue(round(slider.value() + (gain - slider.value()) / self.interpolation_step))
            else:
                slider.setValue(gain)

    def showEvent(self, event) -> None:
        """Repaint the widget when it becomes visible.

        :param event: Qt show event.
        :returns: None.
        """
        super().showEvent(event)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the widget, the visuals live in EQWidgetSliderFrame.

        :param event: Qt paint event.
        :returns: None.
        """
        super().paintEvent(event)