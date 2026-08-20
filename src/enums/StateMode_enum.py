from enum import Enum


class StateMode(Enum):
    """Main window mode."""
    NONE = 0,
    HOME_PAGE = 1,
    PLAYER = 2,
    LOADING = 3,
    OPENING = 4,
