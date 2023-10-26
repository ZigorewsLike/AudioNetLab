import math
import os
import time
from copy import deepcopy
from datetime import timedelta
from gettext import find
from typing import TYPE_CHECKING, Union, Optional, List, Dict, Tuple
from math import atan2, cos, sin, pi

from multipledispatch import dispatch
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.id3 import ID3, ID3NoHeaderError

from PyQt6 import QtMultimedia
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QPoint, QRectF, QRect, QUrl, QDir, pyqtSlot, QSize, QObject
from PyQt6.QtGui import (QPainter, QFont, QPaintEvent, QBrush, QColor, QPen, QMouseEvent, QLinearGradient, QCursor,
                         QWheelEvent, QKeyEvent, QPolygon, QDropEvent, QResizeEvent, QPixmap, QIcon)
from PyQt6.QtWidgets import QWidget, QMessageBox, QApplication, QLabel, QPushButton, QListWidget, QListWidgetItem, \
    QSlider

# AI
import torch
import torchaudio

from src.core.render.graphics_system import GraphPanelAudio
from src.core.log_system import print_d, print_e
from src.emus import PlayerState

if TYPE_CHECKING:
    from src.forms import MainForm


class MetaListItem(QWidget):
    def __init__(self, key: str, values: List[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        tag_str_value: str = ""
        for tag_value in values:
            if isinstance(tag_value, list):
                tag_str_value += ', '.join(tag_value)
            else:
                tag_str_value += str(tag_value)
        self.label = QLabel(self)
        self.label.setText(f'<span style=" font-size:8pt; font-weight: bold; color:#36C942;">{key}:</span> '
                           f'{tag_str_value}')
        self.label.adjustSize()
        self.label.move(5, 0)


class AudioPlayer(QWidget):
    def __init__(self, *args, **kwargs):
        super(AudioPlayer, self).__init__(*args, **kwargs)
        self.mf: Union[MainForm, QWidget] = self.parent()
        self.setAcceptDrops(True)

        self.resize(400, 400)
        self.image_size: int = 120
        self.player_state: PlayerState = PlayerState.NONE

        # region UI
        self.title_tack = QLabel("Tittle", self)
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

        self.position_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_track_position)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.sliderMoved.connect(self.set_track_volume)
        self.volume_slider.move(10, self.image_size + 20)
        self.volume_slider.setFixedWidth(self.image_size)

        self.label_duration_left = QLabel("0:00:00", self)
        self.label_duration_left.adjustSize()

        self.label_duration_right = QLabel("0:00:00", self)
        self.label_duration_right.adjustSize()

        self.audio_graph = GraphPanelAudio(self)
        # endregion

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(50)
        self.player.positionChanged.connect(self.track_position_changed)
        self.player.playbackStateChanged.connect(self.player_state_changed)

        self.change_play_icon()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        # painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        painter.drawPixmap(10, 10, self.track_image)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.meta_list.resize(self.width() - self.image_size - 30, self.image_size - self.meta_list.y() + 50)
        self.position_slider.move(10, self.meta_list.y() + self.meta_list.height() + 25)
        self.position_slider.setFixedWidth(self.width() - 20)
        self.label_duration_right.move(self.width() - 10 - self.label_duration_right.width(),
                                       self.meta_list.y() + self.meta_list.height() + 5)
        self.label_duration_left.move(10, self.meta_list.y() + self.meta_list.height() + 5)

        self.audio_graph.resize(self.width() - 20, 300)
        self.audio_graph.move(10, self.position_slider.y() + self.position_slider.height())

        self.update()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            for path in event.mimeData().urls():
                if path.isLocalFile():
                    self.open_file(path.path()[1:])
                else:
                    self.open_file(str(path))
                break
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        pass

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

    @pyqtSlot('qint64')
    def track_position_changed(self, position: int) -> None:
        self.position_slider.setValue(position)
        position_time = timedelta(milliseconds=position)
        self.label_duration_left.setText(f"{position_time}".split('.', 2)[0])
        self.label_duration_left.adjustSize()

        self.audio_graph.changeCursorPosition.emit(position / self.player.duration())
        # self.audio_graph.change_scale_graph()

    def player_state_changed(self, state: QMediaPlayer.PlaybackState):
        print_d(state)
        if state is QMediaPlayer.PlaybackState.StoppedState:
            self.player.stop()
            self.position_slider.setValue(0)
            self.player_state = PlayerState.WAIT
            self.change_play_icon()

    def open_file_from_ai(self, path) -> None:
        waveform, sample_rate = torchaudio.load(path)
        waveform: torch.Tensor
        waveform_np = waveform.numpy()
        print_d(waveform_np.shape, waveform_np[0], sample_rate)
        self.audio_graph.set_data((waveform_np[0] + 1.0) / 2.0, calc_line=False)
        self.audio_graph.set_shift(0, 1)

    # region Player methods
    def open_file(self, path: str) -> None:
        self.stop_music()
        self.meta_list.clear()
        print_d(f"Open file: {path}")

        # region Meta info
        filename, file_extension = os.path.splitext(os.path.basename(path))
        audio = mutagen.File(path)
        if audio is None:
            print_e(f'Open file error. {filename}')
            return
        print_d('Tags:', audio)
        # endregion

        for key, value in audio.items():
            if key == 'title':
                continue
            item = QListWidgetItem()
            self.meta_list.addItem(item)
            self.meta_list.setItemWidget(item, MetaListItem(key, value))

        url = QUrl.fromLocalFile(path)
        self.player.setSource(url)

        track_name = audio.get('title', None)
        self.title_tack.setText(track_name[0] if track_name is not None else filename)
        self.title_tack.adjustSize()

        self.position_slider.setRange(0, self.player.duration())
        position_time = timedelta(milliseconds=self.player.duration())
        self.label_duration_right.setText(f"{position_time}".split('.', 2)[0])
        self.label_duration_right.adjustSize()

        self.open_file_from_ai(path)

        self.player_state = PlayerState.WAIT
        self.mf.settings.system_settings.open_filename = path
        self.mf.save_config_app()
        if self.mf.settings.player_settings.auto_play:
            self.play_music()

    @pyqtSlot()
    def play_music(self) -> None:
        self.player.play()
        self.player_state = PlayerState.PLAY
        self.change_play_icon()

    @pyqtSlot()
    def pause_music(self) -> None:
        self.player.pause()
        self.player_state = PlayerState.PAUSE
        self.change_play_icon()

    @pyqtSlot()
    def stop_music(self) -> None:
        self.player.stop()
        self.player_state = PlayerState.WAIT
        self.change_play_icon()

    @pyqtSlot(int)
    def set_track_position(self, value: int) -> None:
        self.player.setPosition(value)
        position_time = timedelta(milliseconds=value)
        self.label_duration_left.setText(f"{position_time}".split('.', 2)[0])
        self.label_duration_left.adjustSize()

    @pyqtSlot(int)
    def set_track_volume(self, value: int) -> None:
        self.audio_output.setVolume(value / 100)

    # endregion
