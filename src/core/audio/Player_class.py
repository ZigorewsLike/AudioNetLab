import gc
import math
import os
import time
from copy import deepcopy
from datetime import timedelta, datetime
from gettext import find
from typing import TYPE_CHECKING, Union, Optional, List, Dict, Tuple, Any
from math import atan2, cos, sin, pi

import numpy as np
from multipledispatch import dispatch
import mutagen
import librosa

from PyQt6 import QtMultimedia, QtCore
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QPoint, QRectF, QRect, QUrl, QDir, pyqtSlot, QSize, QObject
from PyQt6.QtGui import (QPainter, QFont, QPaintEvent, QBrush, QColor, QPen, QMouseEvent, QLinearGradient, QCursor,
                         QWheelEvent, QKeyEvent, QPolygon, QDropEvent, QResizeEvent, QPixmap, QIcon, QShowEvent)
from PyQt6.QtWidgets import QWidget, QMessageBox, QApplication, QLabel, QPushButton, QListWidget, QListWidgetItem, \
    QSlider

from src.core.file_system import LastFileProp
from src.core.render.graphics_system import GraphPanelAudio
from src.core.qt_widgets import SimpleSlider
from src.core.log_system import print_d, print_e
from src.enums import PlayerState, StateMode

if TYPE_CHECKING:
    from src.forms import MainForm


class MetaListItem(QWidget):
    def __init__(self, key: str, values: List[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        tag_str_value: str = ""
        try:
            for tag_value in values:
                if isinstance(tag_value, list):
                    tag_str_value += ', '.join(tag_value)
                else:
                    tag_str_value += str(tag_value)
        except Exception as e:
            print_e(e)
            tag_str_value = 'UNKNOWN'
        self.label = QLabel(self)
        self.label.setText(f'<span style=" font-size:8pt; font-weight: bold; color:#36C942;">{key}:</span> '
                           f'{tag_str_value}')
        self.label.adjustSize()
        self.label.move(5, 0)


class AudioPlayer(QWidget):
    positionChanged = QtCore.pyqtSignal(float)

    def __init__(self, mf, *args, **kwargs):
        super(AudioPlayer, self).__init__(*args, **kwargs)
        self.mf: Union[MainForm, QWidget] = mf

        self.resize(400, 400)
        self.image_size: int = 120
        self.player_state: PlayerState = PlayerState.NONE
        self.graph_visible: bool = True

        self.waveform: Optional[np.ndarray] = None
        self.sample_rate: Optional[int] = None

        self.track_meta: Optional[Dict[str, Any]] = None

        # region UI
        self.title_tack = QLabel("Player is empty", self)
        self.title_tack.setStyleSheet("""
        QLabel{
            font-size: 14pt;
        }
        """)
        self.title_tack.move(self.image_size + 20, 5)

        self.track_image = QPixmap(f'res/TrackImage.png')
        self.track_image = self.track_image.scaled(self.image_size, self.image_size,
                                                   Qt.AspectRatioMode.IgnoreAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation)
        print_d(self.track_image.size())

        self.play_button = QPushButton("", self)
        self.play_button.clicked.connect(self.play_button_click)
        self.play_button.resize(self.image_size, self.image_size)
        self.play_button.move(10, 10)
        self.play_button.setIconSize(QSize(60, 60))
        self.play_button.setStyleSheet("""
        QPushButton{
            background-color: transparent;
            border: 0px;
        }
        QPushButton::hover {
            background-color: rgba(1, 1, 1, 0.1);
        }
        QPushButton::pressed {
            background-color: rgba(0, 0, 0, 0.3);
        }
        
        """)

        self.meta_list = QListWidget(self)
        self.meta_list.move(self.image_size + 20, 40)
        self.meta_list.setContentsMargins(5, 5, 5, 5)

        self.position_slider = SimpleSlider(self)
        self.position_slider.set_range(0, 1)
        self.position_slider.sliderMoved.connect(self.set_track_position)

        self.volume_slider = SimpleSlider(self)
        self.volume_slider.set_range(0, 100)
        self.volume_slider.set_value(50)
        self.volume_slider.sliderMoved.connect(self.set_track_volume)
        self.volume_slider.move(10, self.image_size + 20)
        self.volume_slider.setFixedWidth(self.image_size)

        self.label_duration_left = QLabel("0:00:00", self)
        self.label_duration_left.adjustSize()

        self.label_duration_right = QLabel("0:00:00", self)
        self.label_duration_right.adjustSize()

        self.audio_graph = GraphPanelAudio(self)

        self.graph_visible_button = QPushButton("Скрыть", self)
        self.graph_visible_button.clicked.connect(self.switch_visible_graph)
        # endregion

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(50)
        self.player.positionChanged.connect(self.track_position_changed)
        self.player.playbackStateChanged.connect(self.player_state_changed)
        self.player.durationChanged.connect(self.duration_is_changed)

        self.change_play_icon()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        # painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        painter.drawPixmap(10, 10, self.track_image)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.recalc_sizes()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.isVisible():
            self.recalc_sizes()

    def recalc_sizes(self) -> None:
        self.meta_list.resize(self.width() - self.image_size - 30, self.image_size - self.meta_list.y() + 50)
        self.position_slider.move(10, self.meta_list.y() + self.meta_list.height() + 25)
        self.position_slider.setFixedWidth(self.width() - 20)
        self.label_duration_right.move(self.width() - 10 - self.label_duration_right.width(),
                                       self.meta_list.y() + self.meta_list.height() + 5)
        self.label_duration_left.move(10, self.meta_list.y() + self.meta_list.height() + 5)

        self.audio_graph.resize(self.width() - 20, 150)
        self.audio_graph.move(10, self.position_slider.y() + self.position_slider.height() + 10)

        self.graph_visible_button.move(10, self.position_slider.y() + self.position_slider.height() + 10)

        self.update()

    def change_play_icon(self) -> None:
        if self.player_state is PlayerState.PLAY:
            self.play_button.setIcon(QIcon('res/PauseButton.png'))
        else:
            self.play_button.setIcon(QIcon('res/PlayButton.png'))

    @pyqtSlot()
    def play_button_click(self) -> None:
        if self.player_state is PlayerState.WAIT or self.player_state is PlayerState.PAUSE:
            self.play_music()
        elif self.player_state is PlayerState.PLAY:
            self.pause_music()

    @pyqtSlot()
    def switch_visible_graph(self) -> None:
        self.graph_visible = not self.graph_visible
        if not self.graph_visible:
            self.resize(self.width(), self.height() - self.audio_graph.height() + 10)
            self.audio_graph.setVisible(False)
        else:
            self.resize(self.width(), self.height() + self.audio_graph.height() - 10)
            self.audio_graph.setVisible(True)
        self.mf.settings.player_settings.graph_visible = self.graph_visible
        self.mf.resized.emit()

    @pyqtSlot('qint64')
    def track_position_changed(self, position: int) -> None:
        self.position_slider.set_value(position)
        position_time = timedelta(milliseconds=position)
        self.label_duration_left.setText(f"{position_time}".split('.', 2)[0])
        self.label_duration_left.adjustSize()

        if self.player.duration() != 0:
            self.audio_graph.changeCursorPosition.emit(position / self.player.duration())
            self.positionChanged.emit(position / self.player.duration())
            self.audio_graph.change_scale_graph()

    def player_state_changed(self, state: QMediaPlayer.PlaybackState):
        print_d(state)
        if state is QMediaPlayer.PlaybackState.StoppedState:
            self.player.stop()
            self.position_slider.set_value(0)
            self.player_state = PlayerState.WAIT
            self.change_play_icon()

    # region Player methods
    def prepare_to_open_file(self, path: str) -> bool:
        self.stop_music()
        self.meta_list.clear()
        print_d(f"Open file: {path}")

        # region Meta info
        filename, file_extension = os.path.splitext(os.path.basename(path))
        audio = mutagen.File(path)
        if audio is None:
            print_e(f'Open file error. {filename}')
            return False
        print_d('Tags:', audio)
        # endregion

        for key, value in audio.items():
            if key == 'title':
                continue
            item = QListWidgetItem()
            self.meta_list.addItem(item)
            self.meta_list.setItemWidget(item, MetaListItem(key, value))

        track_name = audio.get('title', None)

        pict_tag = audio.get("APIC:", None)
        if pict_tag is not None:
            print_d(pict_tag.data)
        # im = Image.open(BytesIO(pict))
        self.title_tack.setText(track_name[0] if track_name is not None else filename)
        self.title_tack.adjustSize()

        return True

    def open_file_ai(self, path) -> None:
        waveform_np, sample_rate = librosa.load(path)
        # print_d(y.shape, waveform_np.shape)
        print_d(waveform_np.shape, waveform_np[0], sample_rate)
        self.audio_graph.set_data((waveform_np + 1.0) / 2.0, calc_line=False)
        self.audio_graph.set_shift(0, 1)

        self.waveform = waveform_np
        self.sample_rate = sample_rate

    @pyqtSlot('qint64')
    def duration_is_changed(self, duration: int) -> None:
        self.position_slider.set_range(0, duration)
        position_time = timedelta(milliseconds=duration)
        self.label_duration_right.setText(f"{position_time}".split('.', 2)[0])
        self.label_duration_right.adjustSize()

    @pyqtSlot()
    def play_music(self) -> None:
        if self.mf.state is StateMode.PLAYER:
            self.player.play()
            self.player_state = PlayerState.PLAY
            self.change_play_icon()

    @pyqtSlot()
    def pause_music(self) -> None:
        if self.mf.state is StateMode.PLAYER:
            self.player.pause()
            self.player_state = PlayerState.PAUSE
            self.change_play_icon()

    @pyqtSlot()
    def stop_music(self) -> None:
        if self.mf.state is StateMode.PLAYER:
            self.player.stop()
            self.player_state = PlayerState.WAIT
            self.change_play_icon()

    @pyqtSlot(int)
    def set_track_position(self, value: int) -> None:
        if self.mf.state is StateMode.PLAYER:
            self.player.setPosition(value)
            position_time = timedelta(milliseconds=value)
            self.label_duration_left.setText(f"{position_time}".split('.', 2)[0])
            self.label_duration_left.adjustSize()
            self.positionChanged.emit(value / self.player.duration())

    @pyqtSlot(int)
    def set_track_volume(self, value: int) -> None:
        self.audio_output.setVolume(value / 100)

    # endregion
