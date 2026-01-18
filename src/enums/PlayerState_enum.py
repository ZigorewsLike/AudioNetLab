from enum import Enum


class PlayerState(Enum):
    NONE = 0
    WAIT = 1
    PLAY = 2
    PAUSE = 3
    STOP = 4
    OPENING = 5

