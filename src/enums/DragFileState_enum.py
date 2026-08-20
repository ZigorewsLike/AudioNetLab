from enum import Enum


class DragFileState(Enum):
    """State of the dragged file: CORRECT is a supported audio extension."""
    NONE = 0,
    CORRECT = 1,
    INCORRECT = 2
