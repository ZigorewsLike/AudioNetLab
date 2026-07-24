import math
import time
from typing import TYPE_CHECKING, Optional, List

import librosa
import numpy as np
from PyQt6 import QtCore
from PyQt6.QtCore import QObject

from src.global_constants import ONNX_INFERENCE, PATTERN_SIZE, SAMPLING_RATE_AI
from src.core.log_system import print_d
from src.function_lib.audio import get_genre_input_data

if TYPE_CHECKING:
    from src.forms import MainForm


class GenrePredictWorker(QObject):
    """Worker that classifies a track fragment by fragment outside the UI thread.

    Every PATTERN_SIZE second fragment is turned into a librosa feature vector,
    normalised with the training scaler and pushed through the ONNX model.
    Feature vectors are cached in the track registry, so a repeated prediction
    only runs inference.

    :signals: finished (list) - genre index per fragment, preloader_signal (str) - progress text
    """
    finished = QtCore.pyqtSignal(list)
    mf = None  # MainForm
    pattern_length: int = PATTERN_SIZE  # sec
    preloader_signal = QtCore.pyqtSignal(str)
    waveform: Optional[np.ndarray] = None
    sample_rate: Optional[int] = None
    track_id: Optional[int] = None

    def __init__(self):
        """Create the worker, inputs are assigned as attributes before run().

        :returns: None.
        """
        super().__init__()

    def run(self) -> List[int]:
        """Classify the waveform and emit the per fragment genre indexes.

        Uses the explicitly assigned waveform when present, otherwise the track
        currently opened in the player.

        :returns: List[int] - Genre index per fragment, empty when there is nothing to classify.
        """
        if self.waveform is not None:
            waveform = self.waveform
            sample_rate = self.sample_rate
            track_id = self.track_id
        else:
            waveform = self.mf.audio_player.waveform
            sample_rate = self.mf.audio_player.sample_rate
            track_id = self.mf.audio_player.playable_track_id

        start_time = time.time()
        iter_sum_time: float = 0.0

        if waveform is not None:
            predict_index_list: List[int] = []
            waveform = waveform[:, 0].astype(np.float32) / np.iinfo(waveform.dtype).max  # Left channel, [-1, 1]
            target_sr: int = SAMPLING_RATE_AI
            if sample_rate != target_sr:  # The model was trained on SAMPLING_RATE_AI
                waveform = librosa.resample(waveform, orig_sr=sample_rate, target_sr=target_sr)
                sample_rate = target_sr

            sample_len: int = math.ceil(waveform.shape[0] / sample_rate / self.pattern_length)

            # StandardScaler coefficients taken from the training pipeline
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
            input_array: Optional[np.ndarray] = self.mf.file_meta_controller.get_track_librosa_data(track_id=track_id)
            use_cache_data: bool = input_array is not None  # Features already computed for this track

            for step_index, step in enumerate(range(sample_len)):
                self.preloader_signal.emit(f"Классификация жанра {round(step / sample_len * 100)}%")
                if not use_cache_data:
                    waveform_part = waveform[step * sample_rate * self.pattern_length:
                                             (step + 1) * sample_rate * self.pattern_length]

                    input_data = get_genre_input_data(waveform_part, sample_rate)
                    input_data = np.array(input_data)

                    input_data = (input_data - mean) / std
                    input_data = input_data.reshape(1, -1)

                    if input_array is None:
                        input_array = np.array([input_data])
                    else:
                        input_array = np.concatenate((input_array, [input_data]), axis=0)
                else:
                    input_data = input_array[step_index]

                # region Predict
                predict_time = time.time()
                input_name = self.mf.genre_widget.model.get_inputs()[0].name
                output_name = self.mf.genre_widget.model.get_outputs()[0].name

                preds = np.array(self.mf.genre_widget.model.run([output_name],
                                                                {input_name: input_data.astype(np.float32)}))
                preds = preds.squeeze()
                pred = np.argmax(preds)
                # Keep the previous genre on a low confidence fragment to avoid flicker
                if last_predict is not None and preds[pred] < 0.85:
                    pred = last_predict
                else:
                    last_predict = pred
                iter_sum_time += (time.time() - predict_time) * 1000

                predict_index_list.append(int(pred))
                # endregion
            if not use_cache_data:
                self.mf.file_meta_controller.save_track_librosa_data(track_id, input_array)
            self.preloader_signal.emit(f"Классификация жанра 100%")
            print_d(f"Predict time: {(time.time() - start_time) * 1000}ms | IterSUmTime: {iter_sum_time}ms")
            self.finished.emit(predict_index_list)
            return predict_index_list
        self.finished.emit([])
        return []