from enum import Enum


class ProfileDataType(Enum):
    """Kind of measurement in the profiler: a draw call or a math call."""
    NONE = 0,
    DRAW_CALL = 1,
    MATH_CALL = 2,
