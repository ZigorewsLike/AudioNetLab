from typing import Dict, TYPE_CHECKING, List

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, Qt, QEvent
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (QWidget, QLabel, QPushButton, QSlider, QComboBox, QVBoxLayout,
                             QCheckBox, QHBoxLayout, QMessageBox)

from src.core.settings.qt_widgets.SettingsSection_class import SettingsSection

if TYPE_CHECKING:
    from src.forms import MainForm


class SettingsAudioWidget(QWidget):
    """Settings tab for the output device, the streaming buffer and the volume curve."""
    onPresetChanged = QtCore.pyqtSignal(dict)

    def __init__(self, mf, *args, **kwargs):
        """Build the audio settings form.

        :param mf: Main form reference.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf
        self.devices: List[Dict[str, any]] = []

        root = QVBoxLayout(self)

        self.audio_out_device_combo = QComboBox()
        self.audio_out_device_button = QPushButton("")
        self.audio_out_device_button.setFixedWidth(100)
        self.audio_out_device_button.clicked.connect(self.switch_device)

        self.chunk_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.chunk_size_slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
        self.chunk_size_slider.setTickInterval(100)
        self.chunk_size_slider.setRange(2**8, 2**12)
        self.chunk_size_slider.valueChanged.connect(self.chunk_size_changed)
        self.chunk_size_label = QLabel("", self)

        chunk_layout = QHBoxLayout()
        chunk_layout.addWidget(self.chunk_size_slider, 10)
        chunk_layout.addWidget(self.chunk_size_label, 1)

        self.log_volume_checkbox = QCheckBox("")
        self.log_volume_checkbox.stateChanged.connect(self.set_log_volume)

        device_row = QHBoxLayout()
        device_row.addWidget(self.audio_out_device_combo)
        device_row.addWidget(self.audio_out_device_button)

        self.device_section = SettingsSection(self)
        self.device_section.add_full_row(device_row)

        self.parameters_section = SettingsSection(self)
        self.buffer_label = QLabel("")  # Field caption, reached by retranslate_ui
        self.parameters_section.add_row(self.buffer_label, chunk_layout)
        self.parameters_section.add_full_row(self.log_volume_checkbox)

        root.addWidget(self.device_section)
        root.addWidget(self.parameters_section)
        root.addStretch(1)

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
        """Apply the current translation to the texts of this page.

        :returns: None.
        """
        self.audio_out_device_button.setText(self.tr("Switch"))
        self.log_volume_checkbox.setText(self.tr("Logarithmic volume control"))
        self.device_section.set_title(self.tr("Device"))
        self.parameters_section.set_title(self.tr("Parameters"))
        self.buffer_label.setText(self.tr("Buffer size"))

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh the form from the current player state.

        :param event: Qt show event.
        :returns: None.
        """
        super().showEvent(event)
        self.load_data()

    def load_data(self) -> None:
        """Fill the device list and the controls with the active values.

        :returns: None.
        """
        self.audio_out_device_combo.clear()
        self.devices = self.mf.audio_player.get_output_devices()
        for device in self.devices:
            device_text = f"{device.get('hostapi_name')}: {device.get('name')}"
            self.audio_out_device_combo.addItem(device_text)
        default_device = self.mf.audio_player.get_default_output()
        device_text = f"{default_device.get('hostapi_name')}: {default_device.get('name')}"
        self.audio_out_device_combo.setCurrentText(device_text)

        self.chunk_size_slider.setValue(self.mf.audio_player.audio_streamer.get_chunk_size())
        self.log_volume_checkbox.setChecked(self.mf.audio_player.audio_streamer.log_volume)

    def switch_device(self) -> None:
        """Move playback to the selected device and report an unsupported format.

        :returns: None.
        """
        if self.isVisible():
            text_index = self.audio_out_device_combo.currentIndex()
            device_index = self.devices[text_index].get('index')
            if self.mf.audio_player.is_playable:
                if not self.mf.audio_player.switch_device(device_index):
                    error_critical_msg = QMessageBox()
                    error_critical_msg.setText(
                        self.tr("Unable to switch to the device {0}. The format is not supported, "
                                "the system default device is used instead.").format(
                            self.audio_out_device_combo.currentText())
                        + f"\nDevice:{self.devices[text_index]}")
                    error_critical_msg.setIcon(QMessageBox.Icon.Critical)
                    error_critical_msg.setWindowTitle(self.tr("Device switch error"))
                    error_critical_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                    error_critical_msg.exec()
                    self.audio_out_device_combo.setCurrentIndex(0)

    @pyqtSlot(int)
    def set_log_volume(self, _: int) -> None:
        """Switch the volume slider between the linear and the perceptual curve.

        :param _: Checkbox state, unused.
        :returns: None.
        """
        self.mf.audio_player.set_log_volume(self.log_volume_checkbox.isChecked())

    @pyqtSlot(int)
    def chunk_size_changed(self, value: int) -> None:
        """Apply a new streaming buffer size.

        :param value: Buffer size in samples, larger values trade latency for stability.
        :returns: None.
        """
        chunk_size = value
        self.chunk_size_label.setText(f"{chunk_size}")
        self.chunk_size_label.adjustSize()

        self.mf.audio_player.audio_streamer.set_chunk_size(chunk_size)
