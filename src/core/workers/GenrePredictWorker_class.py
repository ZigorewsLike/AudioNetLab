import math
import time
from typing import TYPE_CHECKING, Optional, List

import numpy as np
from PyQt6 import QtCore
from PyQt6.QtCore import QObject

from src.global_constants import ONNX_INFERENCE
from src.core.log_system import print_d
from src.function_lib.audio import get_genre_input_data

if not ONNX_INFERENCE:
    try:
        import torch
    except ImportError as ie:
        ONNX_INFERENCE = True

if TYPE_CHECKING:
    from src.forms import MainForm


class GenrePredictWorker(QObject):
    finished = QtCore.pyqtSignal(list)
    mf = None  # MainForm
    pattern_length: int = 3  # sec
    preloader_signal = QtCore.pyqtSignal(str)
    waveform: Optional[np.ndarray] = None
    sample_rate: Optional[int] = None

    def __init__(self):
        super().__init__()

    def run(self) -> List[int]:
        if not ONNX_INFERENCE:
            device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
            print_d("device:", device)
            self.mf.genre_widget.model.to(device)
        if self.waveform is not None:
            waveform = self.waveform
            sample_rate = self.sample_rate
        else:
            waveform = self.mf.audio_player.waveform
            sample_rate = self.mf.audio_player.sample_rate

        if waveform is not None:
            predict_index_list: List[int] = []

            sample_len: int = math.ceil(waveform.shape[0] / sample_rate / self.pattern_length)
            for step in range(sample_len):
                self.preloader_signal.emit(f"Классификация жанра {round(step / sample_len * 100)}%")
                waveform_part = waveform[step * sample_rate * self.pattern_length:
                                         (step + 1) * sample_rate * self.pattern_length]

                input_data = get_genre_input_data(waveform_part, sample_rate)
                input_data = np.array(input_data)
                # TODO: Тут надо подумать над распределением (Взял коэффы от StandardScaler)
                mean = [6.61490000e+04, 3.79534063e-01, 8.48761481e-02, 1.30859051e-01,
                        2.67638762e-03, 2.19921943e+03, 4.16672699e+05, 2.24138596e+03,
                        1.18271113e+05, 4.56607659e+03, 1.62878997e+06, 1.02578486e-01,
                        2.62012081e-03, -3.64630510e-04, 1.25975714e-02, -3.95501617e-04,
                        5.60155268e-03, 1.24887709e+02, -1.45424643e+02, 2.80890420e+03,
                        1.00988234e+02, 5.88795354e+02, -9.99501395e+00, 3.74137619e+02,
                        3.72437249e+01, 1.83911272e+02, -2.00909897e+00, 1.43817714e+02,
                        1.53954360e+01, 1.07784375e+02, -5.82303365e+00, 9.85051636e+01,
                        1.07666593e+01, 7.47950215e+01, -7.56982540e+00, 7.43093104e+01,
                        8.28366947e+00, 6.88039979e+01, -6.50416778e+00, 6.38126843e+01,
                        4.93631511e+00, 5.77904133e+01, -5.18627201e+00, 5.71303890e+01,
                        2.16462919e+00, 5.40693449e+01, -4.17527144e+00, 5.26782815e+01,
                        1.44824023e+00, 4.99887551e+01, -4.19870598e+00, 5.19627532e+01,
                        7.39942754e-01, 5.24888506e+01, -2.49730557e+00, 5.49738286e+01,
                        -9.17583921e-01, 5.73226142e+01]
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

                input_data = (input_data - mean) / std
                input_data = input_data.reshape(1, -1)

                # region Predict
                if not ONNX_INFERENCE:
                    with torch.set_grad_enabled(False):
                        input_tensor = torch.Tensor(input_data)
                        outputs = self.mf.genre_widget.model(input_tensor.to(device))
                        preds = outputs.data.cpu().numpy().squeeze()
                else:
                    input_name = self.mf.genre_widget.model.get_inputs()[0].name
                    output_name = self.mf.genre_widget.model.get_outputs()[0].name

                    preds = np.array(self.mf.genre_widget.model.run([output_name],
                                                                    {input_name: input_data.astype(np.float32)}))
                    preds = preds.squeeze()
                pred = np.argmax(preds)

                predict_index_list.append(int(pred))
                # endregion
            self.preloader_signal.emit(f"Классификация жанра 100%")
            self.finished.emit(predict_index_list)
            return predict_index_list
        self.finished.emit([])
        return []

