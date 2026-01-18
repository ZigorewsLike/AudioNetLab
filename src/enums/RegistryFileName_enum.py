from enum import Enum


class RegistryFileName(str, Enum):
    NONE = ""
    PREVIEW = "preview.byte"
    TRACK_META = "meta.pckl"
