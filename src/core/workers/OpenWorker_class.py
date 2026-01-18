import math
import time
from typing import TYPE_CHECKING, Optional, List

import numpy as np
from PyQt6 import QtCore
from PyQt6.QtCore import QObject, QUrl

from src.enums import StateMode
from src.global_constants import DEBUG
from src.core.log_system import print_d, print_e

if TYPE_CHECKING:
    from src.forms import MainForm


class OpenFileWorker(QObject):
    finished = QtCore.pyqtSignal(str)
    mf = None  # MainForm
    preloader_signal = QtCore.pyqtSignal(str)
    file_path: str

    def __init__(self):
        super().__init__()

    def run(self) -> None:
        try:
            self.preloader_signal.emit("Открытие файла. Загрузка каких-то данных")
            self.mf.audio_player.open_file(self.file_path)

            self.preloader_signal.emit("Открытие файла. Почти всё")
            self.finished.emit(self.file_path)
        except Exception as e:
            print_e("Worker error:", e)
            self.finished.emit("")


