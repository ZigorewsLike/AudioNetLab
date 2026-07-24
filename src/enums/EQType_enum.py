from enum import Enum


class EQType(Enum):
    """Equalizer flavour: ACTIVE affects playback, PRESET only edits a stored preset."""
    NONE = 0
    ACTIVE = 1
    PRESET = 2
