import math
from typing import Dict, Union, TYPE_CHECKING, Optional, List

import librosa
import numpy as np
import torch

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QPointF, Qt, QPoint
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QLinearGradient, QPen, QFont
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel, QPushButton
from sklearn.preprocessing import StandardScaler

from src.core.log_system import print_d
from src.function_lib.math_lib import median
from src.ai_module.genre_classification.model import GenreClassifier

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

        self.predict_button = QPushButton("Predict", self)
        self.predict_button.move(10, 0)
        self.predict_button.clicked.connect(lambda: self.predict_current())

        self.status_label = QLabel("", self)
        self.status_label.move(self.predict_button.width() + 20, 0)

        self.best_of_label = QLabel("", self)
        self.best_of_label.move(10, 100)

        self.genre_gradient = QLinearGradient(0, 30, self.width(), 60)
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

    # region librosa
    def get_mfcc(self, waveform: Optional[np.ndarray] = None,
                 sample_rate: Optional[int] = None) -> Optional[List[float]]:
        if waveform is None and self.mf.audio_player.waveform is not None:
            waveform = self.mf.audio_player.waveform
            sample_rate = self.mf.audio_player.sample_rate
        if waveform is not None:
            mfcc: np.ndarray = librosa.feature.mfcc(y=waveform, sr=sample_rate)
            mfcc_list: List[float] = []
            for mccf_index in range(20):
                mfcc_part: np.ndarray = mfcc[mccf_index]
                mfcc_list += [mfcc_part.mean(), mfcc_part.var()]

            return mfcc_list
        return None

    def get_tempo(self, waveform: Optional[np.ndarray] = None,
                 sample_rate: Optional[int] = None) -> Optional[float]:
        if waveform is None and self.mf.audio_player.waveform is not None:
            waveform = self.mf.audio_player.waveform
            sample_rate = self.mf.audio_player.sample_rate
        if waveform is not None:
            tempo, _ = librosa.beat.beat_track(y=waveform, sr=sample_rate)
            return tempo
        return None

    def get_chroma_stft(self, waveform: Optional[np.ndarray] = None,
                        sample_rate: Optional[int] = None) -> Optional[List[float]]:
        if waveform is None and self.mf.audio_player.waveform is not None:
            waveform = self.mf.audio_player.waveform
            sample_rate = self.mf.audio_player.sample_rate
        if waveform is not None:
            chroma: np.ndarray = librosa.feature.chroma_stft(y=waveform, sr=sample_rate)
            return [chroma.mean(), chroma.var()]
        return None

    def get_rms(self, waveform: Optional[np.ndarray] = None) -> Optional[List[float]]:
        if waveform is None and self.mf.audio_player.waveform is not None:
            waveform = self.mf.audio_player.waveform
        if waveform is not None:
            rms: np.ndarray = librosa.feature.rms(y=waveform)
            return [rms.mean(), rms.var()]
        return None

    def get_spectral_centroid(self, waveform: Optional[np.ndarray] = None,
                              sample_rate: Optional[int] = None) -> Optional[List[float]]:
        if waveform is None and self.mf.audio_player.waveform is not None:
            waveform = self.mf.audio_player.waveform
            sample_rate = self.mf.audio_player.sample_rate
        if waveform is not None:
            spectral_centroid: np.ndarray = librosa.feature.spectral_centroid(y=waveform, sr=sample_rate)[0]
            return [spectral_centroid.mean(), spectral_centroid.var()]
        return None

    def get_spectral_bandwidth(self, waveform: Optional[np.ndarray] = None,
                               sample_rate: Optional[int] = None) -> Optional[List[float]]:
        if waveform is None and self.mf.audio_player.waveform is not None:
            waveform = self.mf.audio_player.waveform
            sample_rate = self.mf.audio_player.sample_rate
        if waveform is not None:
            spectral_bandwidth: np.ndarray = librosa.feature.spectral_bandwidth(y=waveform, sr=sample_rate)[0]
            return [spectral_bandwidth.mean(), spectral_bandwidth.var()]
        return None

    def get_spectral_rolloff(self, waveform: Optional[np.ndarray] = None,
                             sample_rate: Optional[int] = None) -> Optional[List[float]]:
        if waveform is None and self.mf.audio_player.waveform is not None:
            waveform = self.mf.audio_player.waveform
            sample_rate = self.mf.audio_player.sample_rate
        if waveform is not None:
            spectral_rolloff: np.ndarray = librosa.feature.spectral_rolloff(y=waveform, sr=sample_rate)[0]
            return [spectral_rolloff.mean(), spectral_rolloff.var()]
        return None

    def get_zero_crossing_rate(self, waveform: Optional[np.ndarray] = None) -> Optional[List[float]]:
        if waveform is None and self.mf.audio_player.waveform is not None:
            waveform = self.mf.audio_player.waveform
        if waveform is not None:
            zero_crossing_rate: np.ndarray = librosa.feature.zero_crossing_rate(y=waveform)
            return [zero_crossing_rate.mean(), zero_crossing_rate.var()]
        return None

    def get_harmonics_and_perceptrual(self, waveform: Optional[np.ndarray] = None) -> Optional[List[float]]:
        if waveform is None and self.mf.audio_player.waveform is not None:
            waveform = self.mf.audio_player.waveform
        if waveform is not None:
            y_harm, y_perc = librosa.effects.hpss(y=waveform)
            y_harm: np.ndarray
            y_perc: np.ndarray
            return [y_harm.mean(), y_harm.var(), y_perc.mean(), y_perc.var()]
        return None
    # endregion

    def predict_current(self) -> None:
        predict_index_list = []
        self.genre_gradient = QLinearGradient(0, 30, self.width(), 60)
        sample_len: int = int(self.mf.audio_player.waveform.shape[0] / self.mf.audio_player.sample_rate / 3)
        for step in range(sample_len):
            waveform = self.mf.audio_player.waveform[step * self.mf.audio_player.sample_rate*3:(step + 1) * self.mf.audio_player.sample_rate*3]
            sample_rate = self.mf.audio_player.sample_rate
            input_data: list = []
            input_data += [waveform.shape[0]]
            input_data += self.get_chroma_stft(waveform, sample_rate)
            input_data += self.get_rms(waveform)
            input_data += self.get_spectral_centroid(waveform, sample_rate)
            input_data += self.get_spectral_bandwidth(waveform, sample_rate)
            input_data += self.get_spectral_rolloff(waveform, sample_rate)
            input_data += self.get_zero_crossing_rate(waveform)
            input_data += self.get_harmonics_and_perceptrual(waveform)
            input_data += [self.get_tempo(waveform, sample_rate)]
            input_data += self.get_mfcc(waveform, sample_rate)

            class_index = self.predict_model(np.array(input_data))
            predict_index_list.append(class_index)

            self.genre_gradient.setColorAt(step / sample_len, QColor(self.genre_color[class_index]))
        self.global_results = predict_index_list
        counts = np.bincount(np.array(predict_index_list))

        best_of_text: str = ""
        for inx, count in enumerate(counts):
            best_of_text += f"{self.genre_dict[inx]} : {round(count / counts.sum() * 100, 2)}%\n"
        self.best_of_label.setText(best_of_text)
        self.best_of_label.adjustSize()

        print_d(f"Final genre: {np.argmax(counts)}, name: {self.genre_dict[int(np.argmax(counts))]}")
        self.status_label.setText(f"result: {self.genre_dict[int(np.argmax(counts))]}")
        self.status_label.adjustSize()
        self.update()

    def predict_model(self, data: np.ndarray) -> int:
        with torch.set_grad_enabled(False):
            # data preparation
            # TODO: Тут надо подумать над распределением (Взял коэффы от StandardScaler)
            mean = [6.61490000e+04,  3.79534063e-01,  8.48761481e-02,  1.30859051e-01,
                    2.67638762e-03,  2.19921943e+03,  4.16672699e+05,  2.24138596e+03,
                    1.18271113e+05,  4.56607659e+03,  1.62878997e+06,  1.02578486e-01,
                    2.62012081e-03, -3.64630510e-04,  1.25975714e-02, -3.95501617e-04,
                    5.60155268e-03,  1.24887709e+02, -1.45424643e+02,  2.80890420e+03,
                    1.00988234e+02,  5.88795354e+02, -9.99501395e+00,  3.74137619e+02,
                    3.72437249e+01,  1.83911272e+02, -2.00909897e+00,  1.43817714e+02,
                    1.53954360e+01,  1.07784375e+02, -5.82303365e+00,  9.85051636e+01,
                    1.07666593e+01,  7.47950215e+01, -7.56982540e+00,  7.43093104e+01,
                    8.28366947e+00,  6.88039979e+01, -6.50416778e+00,  6.38126843e+01,
                    4.93631511e+00,  5.77904133e+01, -5.18627201e+00,  5.71303890e+01,
                    2.16462919e+00,  5.40693449e+01, -4.17527144e+00,  5.26782815e+01,
                    1.44824023e+00,  4.99887551e+01, -4.19870598e+00,  5.19627532e+01,
                    7.39942754e-01,  5.24888506e+01, -2.49730557e+00,  5.49738286e+01,
                    -9.17583921e-01,  5.73226142e+01]
            std = [1.00000000e+00, 9.04612345e-02, 9.63613953e-03, 6.85419623e-02,
                   3.58544858e-03, 7.51822979e+02, 4.34942666e+05, 5.43827228e+02,
                   1.01345391e+05, 1.64198315e+03, 1.48932366e+06, 4.56489017e-02,
                   3.61337954e-03, 1.69935396e-03, 1.26326091e-02, 1.10776697e-03,
                   6.65289162e-03, 3.29100290e+01, 1.06451022e+02, 2.59612687e+03,
                   3.46714428e+01, 4.59682218e+02, 2.39713223e+01, 2.94455840e+02,
                   1.78035685e+01, 1.33157586e+02, 1.35680381e+01, 1.09267114e+02,
                   1.26518792e+01, 7.58965988e+01, 1.10881432e+01, 6.55334016e+01,
                   1.11224505e+01, 4.58789784e+01, 9.36795340e+00, 4.47307728e+01,
                   8.84111511e+00, 4.18621080e+01, 7.82077669e+00, 4.02163441e+01,
                   7.56280870e+00, 3.74791371e+01, 7.13169205e+00, 3.57447500e+01,
                   6.08397841e+00, 3.77137040e+01, 5.92916063e+00, 3.72501019e+01,
                   5.73486235e+00, 3.44410924e+01, 5.67709468e+00, 3.63988475e+01,
                   5.18105399e+00, 3.81752093e+01, 5.11154342e+00, 4.15835954e+01,
                   5.25298031e+00, 4.64418872e+01]
            data = (data - mean) / std
            # endregion

            data = data.reshape(1, -1)
            outputs = self.model(torch.Tensor(data))
            # print_d(outputs)
            preds = outputs.data.cpu().numpy().squeeze()
            pred = np.argmax(preds)

            # print_d(f"Predict: {pred}, name: {self.genre_dict[int(pred)]}")

            return int(pred)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(10, 30, self.width() - 21, 60, QBrush(self.genre_gradient))
        if self.drawing_text_pos is not None and len(self.global_results) > 0:
            painter.setPen(QPen(Qt.GlobalColor.white, 1.0, Qt.PenStyle.DashLine))
            painter.setFont(QFont("Arial", 14))
            painter.drawLine(self.drawing_text_pos.x(), 30, self.drawing_text_pos.x(), 90)

            painter.setCompositionMode(QPainter.CompositionMode.RasterOp_SourceXorDestination)
            index_factor: float = (self.drawing_text_pos.x() - 10) / (self.width() - 21)
            index: int = median(0, round(len(self.global_results) * index_factor), len(self.global_results) - 1)
            painter.drawText(self.drawing_text_pos, self.genre_dict[self.global_results[index]])
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        self.drawing_text_pos = event.pos()
        self.update()

    def leaveEvent(self, a0) -> None:
        self.drawing_text_pos = None



