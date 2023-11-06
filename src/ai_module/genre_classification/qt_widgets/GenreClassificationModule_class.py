import math
from typing import Dict, Union, TYPE_CHECKING, Optional, List

import librosa
import numpy as np
import torch

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QPointF, Qt, QPoint, QThread
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QLinearGradient, QPen, QFont, \
    QResizeEvent
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel, QPushButton
from sklearn.preprocessing import StandardScaler

from src.core.log_system import print_d
from src.function_lib.math_lib import median
from src.ai_module.genre_classification.model import GenreClassifier
from src.core.workers import GenrePredictWorker

if TYPE_CHECKING:
    from src.forms import MainForm


class GenreClassifierModule(QWidget):
    def __init__(self, model_path: str, main_form, *args, **kwargs):
        super(GenreClassifierModule, self).__init__(*args, **kwargs)
        self.model_path: str = model_path
        self.setMouseTracking(True)

        self.model = GenreClassifier()
        self.model_path = model_path

        self.mf: Union[QWidget, MainForm] = main_form
        self.graph_y: int = 60
        self.graph_height: int = 60

        self.work_thread = QThread(self)
        self.worker = GenrePredictWorker()
        self.worker.mf = self.mf
        self.worker.finished.connect(self.predict_finished)
        self.worker.preloader_signal.connect(self.mf.preloader.set_help_text)

        self.predict_button = QPushButton("Predict", self)
        self.predict_button.move(10, 5)
        self.predict_button.clicked.connect(lambda: self.predict_current())

        self.status_label = QLabel("", self)
        self.status_label.move(self.predict_button.width() + 20, 5)

        self.best_of_label = QLabel("", self)
        self.best_of_label.move(10, self.graph_y + self.graph_height + 10)

        self.genre_gradient = QLinearGradient(0, 0, self.width(), 0)
        self.genre_gradient.setColorAt(0.0, QColor("#2A2A2A"))
        self.genre_gradient.setColorAt(1.0, QColor("#2A2A2A"))
        self.global_results = []
        self.drawing_text_pos: Optional[QPoint] = None

        self.genre_dict: Dict[int, str] = {
            0: "blues",
            1: "classical",
            2: "country",
            3: "disco",
            4: "hiphop",
            5: "jazz",
            6: "metal",
            7: "pop",
            8: "reggae",
            9: "rock"
        }

        self.genre_color: Dict[int, str] = {
            3: "#742CFA",
            6: "#FA474A",
            8: "#D1FA58",
            0: "#6A9EFA",
            9: "#FA7543",
            1: "#6AFAD2",
            5: "#56FA86",
            4: "#DB81FA",
            2: "#FAF550",
            7: "#ADBDFA",
        }

    def load_model(self) -> None:
        self.model.classifier.load_state_dict(torch.load(self.model_path, map_location='cpu'))
        self.model.eval()

    def predict_current(self) -> None:
        self.worker.moveToThread(self.work_thread)
        self.work_thread.started.connect(self.worker.run)
        self.work_thread.start()
        self.mf.preloader.setVisible(True)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.global_results:
            self.genre_gradient = QLinearGradient(0, 0, self.width(), 0)

            for step in range(len(self.global_results)):
                self.genre_gradient.setColorAt(step / len(self.global_results),
                                               QColor(self.genre_color[self.global_results[step]]))
            self.update()

    @pyqtSlot(list)
    def predict_finished(self, out: List[int]) -> None:
        self.genre_gradient = QLinearGradient(0, 0, self.width(), 0)
        sample_len: int = int(self.mf.audio_player.waveform.shape[0] / self.mf.audio_player.sample_rate / 3)
        for step in range(sample_len):
            self.genre_gradient.setColorAt(step / sample_len, QColor(self.genre_color[out[step]]))

        self.global_results = out
        counts = np.bincount(np.array(out))

        best_of_text: str = ""
        for inx, count in enumerate(counts):
            best_of_text += (f"<span style=' font-size:8pt; font-weight: bold; color:#4477C9;'>{self.genre_dict[inx]}"
                             f"</span> : {round(count / counts.sum() * 100, 2)}%<br>")
        self.best_of_label.setText(best_of_text)
        self.best_of_label.adjustSize()

        print_d(f"Final genre: {np.argmax(counts)}, name: {self.genre_dict[int(np.argmax(counts))]}")
        self.status_label.setText(f"<span style=' font-size:8pt; font-weight: bold; color:#4477C9;'>ИТОГ:</span> "
                                  f"{self.genre_dict[int(np.argmax(counts))]}")
        self.status_label.adjustSize()
        self.update()

        self.mf.preloader.setVisible(False)

        self.work_thread.exit(0)
        self.worker = GenrePredictWorker()
        self.worker.mf = self.mf
        self.worker.finished.connect(self.predict_finished)
        self.worker.preloader_signal.connect(self.mf.preloader.set_help_text)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(10, self.graph_y, self.width() - 21, self.graph_height, QBrush(self.genre_gradient))

        if self.drawing_text_pos is not None and len(self.global_results) > 0:
            painter.setPen(QPen(Qt.GlobalColor.white, 1.0, Qt.PenStyle.DashLine))
            painter.setFont(QFont("Arial", 14))
            painter.drawLine(self.drawing_text_pos.x(), self.graph_y, self.drawing_text_pos.x(),
                             self.graph_y + self.graph_height)

            # painter.setCompositionMode(QPainter.CompositionMode.RasterOp_SourceXorDestination)
            index_factor: float = (self.drawing_text_pos.x() - 10) / (self.width() - 21)
            index: int = median(0, round(len(self.global_results) * index_factor), len(self.global_results) - 1)
            genre_text: str = self.genre_dict[self.global_results[index]]
            genre_text_width: int = painter.fontMetrics().boundingRect(genre_text).width()
            painter.drawText(int(self.drawing_text_pos.x() - genre_text_width/2), self.graph_y - 10, genre_text)
            # painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        if self.graph_y <= event.pos().y() <= self.graph_y + self.graph_height:
            self.drawing_text_pos = event.pos()
            self.update()

    def leaveEvent(self, a0) -> None:
        self.drawing_text_pos = None



