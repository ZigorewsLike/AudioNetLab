import math
import time
from typing import TYPE_CHECKING, Optional, List

import librosa
import numpy as np
from PyQt6 import QtCore
from PyQt6.QtCore import QObject

from src.global_constants import ONNX_INFERENCE, PATTERN_SIZE
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
    pattern_length: int = PATTERN_SIZE  # sec
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

        start_time = time.time()
        iter_sum_time: float = 0.0

        if waveform is not None:
            predict_index_list: List[int] = []
            waveform = waveform[:, 0].astype(np.float32) / np.iinfo(waveform.dtype).max
            target_sr: int = 22050
            if sample_rate != target_sr:
                waveform = librosa.resample(waveform, orig_sr=sample_rate, target_sr=target_sr)
                sample_rate = target_sr

            sample_len: int = math.ceil(waveform.shape[0] / sample_rate / self.pattern_length)

            # TODO: Тут надо подумать над распределением (Взял коэффы от StandardScaler)
            mean = [3.78439426e-01, 8.29347338e-02, 1.79139561e-01, 3.35948677e-03,
                    1.90030846e+03, 4.02072421e+05, 2.09221961e+03, 1.59393196e+05,
                    3.92067496e+03, 1.83378160e+06, 8.33124954e-02, 1.93341645e-03,
                    -3.58528929e-04, 2.79848454e-02, 3.25296368e-05, 7.43420408e-03,
                    1.24595710e+02, -1.36013167e+02, 2.76943874e+03, 1.12232118e+02,
                    7.14326792e+02, -3.08710817e+00, 3.58029294e+02, 2.66914436e+01,
                    1.80167852e+02, 2.82162079e+00, 1.26734499e+02, 7.77754136e+00,
                    9.52575915e+01, -1.47999770e+00, 7.99769735e+01, 3.36825122e+00,
                    6.69571396e+01, -3.65315397e+00, 6.29780653e+01, 1.85228599e+00,
                    5.87162213e+01, -3.91181012e+00, 5.45275724e+01, 8.32806666e-01,
                    5.07300193e+01, -3.87692657e+00, 4.99441298e+01, -1.64660454e-01,
                    4.73346287e+01, -3.88341006e+00, 4.54723794e+01, -1.87431403e-01,
                    4.36337517e+01, -4.13741572e+00, 4.34649557e+01, -8.21089090e-03,
                    4.42399132e+01, -3.34129852e+00, 4.60554918e+01, -3.72132951e-01,
                    4.75695794e+01]
            std = [1.06726843e-01, 1.18269274e-02, 1.01265456e-01, 4.52749788e-03,
                   7.59503415e+02, 4.87156523e+05, 5.84705461e+02, 1.62890076e+05,
                   1.67367682e+03, 1.88088474e+06, 4.83544512e-02, 3.47683825e-03,
                   2.35562656e-02, 3.18296135e-02, 1.98921949e-03, 1.03651317e-02,
                   3.43497539e+01, 1.13603137e+02, 3.43477189e+03, 4.18550608e+01,
                   6.92428556e+02, 2.82094866e+01, 3.46893327e+02, 1.70646757e+01,
                   1.64850808e+02, 1.40152041e+01, 1.16355216e+02, 1.18270301e+01,
                   8.32914497e+01, 1.00017675e+01, 6.54312099e+01, 9.69189944e+00,
                   5.46982222e+01, 8.58450047e+00, 4.95028947e+01, 8.25835013e+00,
                   4.39520387e+01, 7.87250066e+00, 4.08558374e+01, 7.35845446e+00,
                   3.77642333e+01, 6.94858222e+00, 3.81120692e+01, 6.83990018e+00,
                   3.65915382e+01, 6.46889724e+00, 3.50061255e+01, 6.37607793e+00,
                   3.36791320e+01, 6.03764829e+00, 3.47116258e+01, 5.80303611e+00,
                   3.64991275e+01, 5.87719984e+00, 3.96594223e+01, 6.09289502e+00,
                   4.44330652e+01]

            last_predict: Optional[int] = None

            for step in range(sample_len):
                self.preloader_signal.emit(f"Классификация жанра {round(step / sample_len * 100)}%")
                waveform_part = waveform[step * sample_rate * self.pattern_length:
                                         (step + 1) * sample_rate * self.pattern_length]

                input_data = get_genre_input_data(waveform_part, sample_rate)
                input_data = np.array(input_data)

                # mean = [4.65794183e-01, 7.56923074e-02, 1.75278169e-01, 3.53687662e-03,
                #         2.36513015e+03, 8.65998300e+05, 2.90494794e+03, 4.84263694e+05,
                #         4.81949597e+03, 4.16501501e+06, 4.80947586e-02, 9.56769801e-04,
                #         -3.48522517e-04, 2.93626296e-02, 3.34480087e-06, 5.69036781e-03,
                #         1.39183726e+02, -1.91072294e+02, 2.37301114e+03, 1.59078602e+02,
                #         6.75706720e+02, -1.88325523e+01, 3.48202761e+02, 3.56565234e+01,
                #         2.12379951e+02, -1.52812168e+00, 1.62954354e+02, 1.69534464e+01,
                #         1.07463146e+02, -5.18542953e+00, 8.58433578e+01, 8.20993444e+00,
                #         7.11997186e+01, -3.38350816e+00, 6.44747266e+01, 3.16680723e+00,
                #         5.84344926e+01, -2.98458318e+00, 5.31788696e+01, 1.89226012e+00,
                #         4.87689249e+01, -2.64430875e+00, 4.56208247e+01, 6.60866663e-01,
                #         4.27977404e+01, -2.07463014e+00, 4.19299321e+01, -5.57927175e-01,
                #         4.03947766e+01, -2.05823175e+00, 3.89586422e+01, -7.81601063e-01,
                #         3.72989379e+01, -1.44632929e+00, 3.65980088e+01, -1.41274723e+00,
                #         3.57718628e+01]
                # std = [1.34538276e-01, 1.83422578e-02, 1.04214487e-01, 5.07240789e-03,
                #        1.19858623e+03, 1.35105118e+06, 1.06031667e+03, 5.40962425e+05,
                #        2.68551526e+03, 5.44036557e+06, 3.57847893e-02, 2.37333131e-03,
                #        2.54191743e-02, 3.47412696e-02, 7.91604646e-03, 8.49746226e-03,
                #        4.62836146e+01, 1.13558014e+02, 3.03508051e+03, 4.29392635e+01,
                #        7.14188402e+02, 3.49900998e+01, 3.81109975e+02, 2.18456206e+01,
                #        2.15433274e+02, 1.80858464e+01, 1.50943534e+02, 1.50182327e+01,
                #        9.81591260e+01, 1.28878977e+01, 7.40304476e+01, 1.14847443e+01,
                #        5.82715215e+01, 9.89746341e+00, 5.23177415e+01, 1.02060374e+01,
                #        4.69283439e+01, 8.43668452e+00, 4.12172066e+01, 8.74769353e+00,
                #        3.71584428e+01, 7.77320893e+00, 3.52159278e+01, 7.79376749e+00,
                #        3.26370998e+01, 7.07310210e+00, 3.24069896e+01, 7.30336456e+00,
                #        3.22349163e+01, 6.63882341e+00, 3.05405514e+01, 6.87173314e+00,
                #        2.90217838e+01, 6.35420504e+00, 2.81950325e+01, 6.52260829e+00,
                #        2.81537207e+01]

                input_data = (input_data - mean) / std
                input_data = input_data.reshape(1, -1)

                # region Predict
                predict_time = time.time()
                input_name = self.mf.genre_widget.model.get_inputs()[0].name
                output_name = self.mf.genre_widget.model.get_outputs()[0].name

                preds = np.array(self.mf.genre_widget.model.run([output_name],
                                                                {input_name: input_data.astype(np.float32)}))
                preds = preds.squeeze()
                print_d(step, (preds * 100).round(1))
                pred = np.argmax(preds)
                if last_predict is not None and preds[pred] < 0.85:
                    pred = last_predict
                else:
                    last_predict = pred
                iter_sum_time += (time.time() - predict_time) * 1000
                # print_d(f"Predict iter time: {(time.time() - predict_time) * 1000}ms")

                predict_index_list.append(int(pred))
                # endregion
            self.preloader_signal.emit(f"Классификация жанра 100%")
            print_d(f"Predict time: {(time.time() - start_time) * 1000}ms | IterSUmTime: {iter_sum_time}ms")
            self.finished.emit(predict_index_list)
            return predict_index_list
        self.finished.emit([])
        return []

