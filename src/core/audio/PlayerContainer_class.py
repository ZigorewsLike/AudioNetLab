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
from mutagen.flac import FLAC
from mutagen.id3 import APIC
from mutagen.mp3 import MP3
import librosa

from PyQt6 import QtMultimedia, QtCore
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QPoint, QRectF, QRect, QUrl, QDir, pyqtSlot, QSize, QObject
from PyQt6.QtGui import (QPainter, QFont, QPaintEvent, QBrush, QColor, QPen, QMouseEvent, QLinearGradient, QCursor,
                         QWheelEvent, QKeyEvent, QPolygon, QDropEvent, QResizeEvent, QPixmap, QIcon, QShowEvent, QImage)
from PyQt6.QtWidgets import QWidget, QMessageBox, QApplication, QLabel, QPushButton, QListWidget, QListWidgetItem, \
    QSlider

from src.core.file_system import LastFileProp
from src.core.qt_widgets import SimpleSlider
from src.core.log_system import print_d, print_e
from src.enums import PlayerState, StateMode
from .Player_class import AudioPlayer
from src.global_constants import PROFILE

if TYPE_CHECKING:
    from src.forms import MainForm


class AudioPlayerContainer(QWidget):
    def __init__(self, mf, *args, **kwargs):
        super(AudioPlayerContainer, self).__init__(*args, **kwargs)
        self.mf: Union[MainForm, QWidget] = mf

        self.audio_player = AudioPlayer(self.mf, self)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)

        self.audio_player.move(0, self.height() - self.audio_player.height())

