from enum import Enum


class RegistryFileName(str, Enum):
    NONE = ""
    PREVIEW = "preview.byte"
    TRACK_META = "meta.pckl"
    LIBROSA_DATA = "librosa_data.npy"
    TRANSCRIPTION = "transcription.pckl"
