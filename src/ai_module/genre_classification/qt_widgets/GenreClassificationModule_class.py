import math
from typing import Dict, Union, TYPE_CHECKING

import numpy as np
import torch

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel

from src.core.log_system import print_d
from src.function_lib.math_lib import median
from src.ai_module.genre_classification.model import GenreClassifier

if TYPE_CHECKING:
    from src.forms import MainForm


class GenreClassifierModule(QWidget):
    def __init__(self, model_path: str, main_form, *args, **kwargs):
        super(GenreClassifierModule, self).__init__(*args, **kwargs)
        self.model_path: str = model_path

        self.model = GenreClassifier()
        self.model_path = model_path

        self.mf: Union[QWidget, MainForm] = main_form

        self.status_label = QLabel("Load...", self)

        self.genre_dict: Dict[int, str] = {
            0: "disco",
            1: "metal",
            2: "reggae",
            3: "blues",
            4: "rock",
            5: "classical",
            6: "jazz",
            7: "hiphop",
            8: "country",
            9: "pop"
        }

    def load_model(self) -> None:
        self.model.classifier.load_state_dict(torch.load(self.model_path, map_location='cpu'))
        self.model.eval()

    def predict_model(self, data: np.ndarray) -> int:
        outputs = self.model(data)
        _, preds = torch.max(outputs, 1)

        print_d(f"Predict: {preds}")

        return preds


