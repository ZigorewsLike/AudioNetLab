from typing import Optional, List

import librosa
import numpy as np


# region librosa
def get_mfcc(waveform: Optional[np.ndarray] = None,
             sample_rate: Optional[int] = None) -> Optional[List[float]]:
    if waveform is not None:
        mfcc: np.ndarray = librosa.feature.mfcc(y=waveform, sr=sample_rate)
        mfcc_list: List[float] = []
        for mccf_index in range(20):
            mfcc_part: np.ndarray = mfcc[mccf_index]
            mfcc_list += [mfcc_part.mean(), mfcc_part.var()]

        return mfcc_list
    return None


def get_tempo(waveform: Optional[np.ndarray] = None,
              sample_rate: Optional[int] = None) -> Optional[float]:
    if waveform is not None:
        tempo, _ = librosa.beat.beat_track(y=waveform, sr=sample_rate)
        return tempo
    return None


def get_chroma_stft(waveform: Optional[np.ndarray] = None,
                    sample_rate: Optional[int] = None) -> Optional[List[float]]:
    if waveform is not None:
        chroma: np.ndarray = librosa.feature.chroma_stft(y=waveform, sr=sample_rate)
        return [chroma.mean(), chroma.var()]
    return None


def get_rms(waveform: Optional[np.ndarray] = None) -> Optional[List[float]]:
    if waveform is not None:
        rms: np.ndarray = librosa.feature.rms(y=waveform)
        return [rms.mean(), rms.var()]
    return None


def get_spectral_centroid(waveform: Optional[np.ndarray] = None,
                          sample_rate: Optional[int] = None) -> Optional[List[float]]:
    if waveform is not None:
        spectral_centroid: np.ndarray = librosa.feature.spectral_centroid(y=waveform, sr=sample_rate)[0]
        return [spectral_centroid.mean(), spectral_centroid.var()]
    return None


def get_spectral_bandwidth(waveform: Optional[np.ndarray] = None,
                           sample_rate: Optional[int] = None) -> Optional[List[float]]:
    if waveform is not None:
        spectral_bandwidth: np.ndarray = librosa.feature.spectral_bandwidth(y=waveform, sr=sample_rate)[0]
        return [spectral_bandwidth.mean(), spectral_bandwidth.var()]
    return None


def get_spectral_rolloff(waveform: Optional[np.ndarray] = None,
                         sample_rate: Optional[int] = None) -> Optional[List[float]]:
    if waveform is not None:
        spectral_rolloff: np.ndarray = librosa.feature.spectral_rolloff(y=waveform, sr=sample_rate)[0]
        return [spectral_rolloff.mean(), spectral_rolloff.var()]
    return None


def get_zero_crossing_rate(waveform: Optional[np.ndarray] = None) -> Optional[List[float]]:
    if waveform is not None:
        zero_crossing_rate: np.ndarray = librosa.feature.zero_crossing_rate(y=waveform)
        return [zero_crossing_rate.mean(), zero_crossing_rate.var()]
    return None


def get_harmonics_and_perceptrual(waveform: Optional[np.ndarray] = None) -> Optional[List[float]]:
    if waveform is not None:
        y_harm, y_perc = librosa.effects.hpss(y=waveform)
        y_harm: np.ndarray
        y_perc: np.ndarray
        return [y_harm.mean(), y_harm.var(), y_perc.mean(), y_perc.var()]
    return None
# endregion


def get_genre_input_data(waveform: Optional[np.ndarray] = None, sample_rate: Optional[int] = None) -> List[float]:
    input_data: list = []
    input_data += get_chroma_stft(waveform, sample_rate)
    input_data += get_rms(waveform)
    input_data += get_spectral_centroid(waveform, sample_rate)
    input_data += get_spectral_bandwidth(waveform, sample_rate)
    input_data += get_spectral_rolloff(waveform, sample_rate)
    input_data += get_zero_crossing_rate(waveform)
    input_data += get_harmonics_and_perceptrual(waveform)
    input_data += [get_tempo(waveform, sample_rate)]
    input_data += get_mfcc(waveform, sample_rate)

    return input_data
