from enum import Enum


class RegistryFileName(str, Enum):
    """File names inside the per track registry folder data/registry/<id>."""
    NONE = ""
    PREVIEW = "preview.byte"
    TRACK_META = "meta.pckl"
    LIBROSA_DATA = "librosa_data.npy"
    TRANSCRIPTION = "transcription.pckl"
