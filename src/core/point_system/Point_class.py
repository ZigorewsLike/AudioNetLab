from dataclasses import dataclass
from math import sqrt
from typing import Union, Tuple

from multipledispatch import dispatch

from PyQt6.QtCore import QPoint


class Point:
    def __init__(self, x: Union[int, float] = 0, y: Union[int, float] = 0):
        self.x = float(x)
        self.y = float(y)

    @classmethod
    def from_qt(cls, point: QPoint):
        return cls(point.x(), point.y())

    @classmethod
    def from_str(cls, text: str):
        x, y = text.split(":")[:2]
        return cls(float(x), float(y))

    def __add__(self, other):
        if isinstance(other, Point):
            return Point(self.x + other.x, self.y + other.y)
        elif isinstance(other, QPoint):
            return Point(self.x + other.x(), self.y + other.y())
        return Point(self.x + other, self.y + other)

    def __iadd__(self, other):
        return self + other

    def __sub__(self, other):
        return self + (other * -1)

    def __repr__(self):
        cls = self.__class__
        return f"<{cls.__module__}.{cls.__qualname__}({self.x}, {self.y})>"

    def __isub__(self, other):
        return self - other

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __ne__(self, other):
        return not self == other

    def __truediv__(self, other):
        if type(other) != Point:
            return Point(self.x / other, self.y / other)
        return Point(self.x / other.x, self.y / other.y)

    def __mul__(self, other):
        if type(other) != Point:
            return Point(self.x * other, self.y * other)
        return Point(self.x * other.x, self.y * other.y)

    def __imul__(self, other):
        return self * other

    def __str__(self):
        return f"x: {self.x}, y: {self.y}"

    def __le__(self, other):
        return self.x <= other.x and self.y <= other.y

    def __lt__(self, other):
        if type(other) != Point:
            return self.x < other and self.y < other
        return self.x < other.x and self.y < other.y

    def __ge__(self, other):
        return self.x >= other.x and self.y >= other.y

    def __round__(self, n=None):
        point = self.copy()
        point.x = round(point.x, n)
        point.y = round(point.y, n)
        return point

    def __neg__(self):
        return Point(-self.x, -self.y)

    def convert(self, point: QPoint):
        self.x = float(point.x())
        self.y = float(point.y())

    def to_str(self) -> str:
        return f"{self.x}:{self.y}"

    def qt(self):
        return QPoint(int(self.x), int(self.y))

    # Length between points
    def lbp(self, other):
        return sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

    def to_list(self):
        return [self.x, self.y]

    def to_list_2d(self):
        return [self.x, self.y]

    def copy(self):
        return Point(self.x, self.y)

    def set_shift(self, shift_point):
        self.x += shift_point.x
        self.y += shift_point.y

    def as_int(self):
        self.x = int(self.x)
        self.y = int(self.y)

    @property
    def ix(self) -> int:
        """
        `self.x` as int
        :return: int
        """
        return int(self.x)

    @property
    def iy(self) -> int:
        """
        `self.y` as int
        :return: int
        """
        return int(self.y)

    @property
    def xy(self) -> Tuple[float, float]:
        return self.x, self.y

    @xy.setter
    def xy(self, tuple_pos: Tuple[float, float]) -> None:
        self.x, self.y = tuple_pos


class Point3d:
    def __init__(self, x=0., y=0., z=0.):
        self.x: float = x
        self.y: float = y
        self.z: float = z

    def __str__(self):
        return f"Point3d({self.x}, {self.y}, {self.z})"

    def __truediv__(self, other):
        if not isinstance(other, Point3d):
            if other != 0:
                return Point3d(self.x / other, self.y / other, self.z / other)
            return Point3d(0, 0, 0)
        n_x = self.x / other.x if other.x != 0 else 0
        n_y = self.y / other.y if other.y != 0 else 0
        n_z = self.z / other.z if other.z != 0 else 0
        return Point3d(n_x, n_y, n_z)

    def __itruediv__(self, other):
        if not isinstance(other, Point3d):
            return Point3d(self.x / other, self.y / other, self.z / other)
        return Point3d(self.x / other.x, self.y / other.y, self.z / other.z)

    def __round__(self, n=None):
        if n is None:
            n = 1
        point = Point3d()
        point.x = round(point.x, n)
        point.y = round(point.y, n)
        point.z = round(point.z, n)
        return point

    def __eq__(self, other):
        if not isinstance(other, Point3d):
            return self.x == other and self.y == other and self.z == other
        return self.x == other.x and self.y == other.y and self.z == other.z

    def __ne__(self, other):
        return not self == other

    @property
    def xy(self):
        return Point(self.x, self.y)

    def from_str(self, string: str) -> None:
        string_array = string.replace("Point3d(", "").replace(")", "").split(', ')
        self.x, self.y, self.z = [float(val) for val in string_array]


@dispatch(Point, Point)
def lbp(point1: Point, point2: Point):
    return sqrt((point1.x - point2.x) ** 2 + (point1.y - point2.y) ** 2)


@dispatch(QPoint, QPoint)
def lbp(point1: QPoint, point2: QPoint):
    return sqrt((point1.x() - point2.x()) ** 2 + (point1.y() - point2.y()) ** 2)
