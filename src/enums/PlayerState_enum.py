from enum import Enum


class PlayerState(Enum):
    """Playback state: NONE nothing loaded, WAIT ready, OPENING file is being decoded."""
    NONE = 0
    WAIT = 1
    PLAY = 2
    PAUSE = 3
    STOP = 4
    OPENING = 5

