import os

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPolygonF


def array2d_to_qpolygonf(xdata, ydata) -> QPolygonF:
    """
    From https://github.com/PlotPyStack/PythonQwt/blob/master/qwt/plot_curve.py#L67C5-L67C25

    Utility function to convert two 1D-NumPy arrays representing curve data
    (X-axis, Y-axis data) into a single polyline (QtGui.PolygonF object).
    This feature is compatible with PyQt5 and PySide6 (requires QtPy).

    License/copyright: MIT License © Pierre Raybaut 2020-2021.

    :param numpy.ndarray xdata: 1D-NumPy array
    :param numpy.ndarray ydata: 1D-NumPy array
    :return: Polyline
    :rtype: QtGui.QPolygonF
    """
    if not (xdata.size == ydata.size == xdata.shape[0] == ydata.shape[0]):
        raise ValueError("Arguments must be 1D NumPy arrays with same size")
    size = xdata.size
    polyline = QPolygonF([QPointF(0, 0)] * size)
    buffer = polyline.data()
    buffer.setsize(16 * size)  # 16 bytes per point: 8 bytes per X,Y value (float64)
    memory = np.frombuffer(buffer, np.float64)
    memory[: (size - 1) * 2 + 1: 2] = np.array(xdata, dtype=np.float64, copy=False)
    memory[1: (size - 1) * 2 + 2: 2] = np.array(ydata, dtype=np.float64, copy=False)
    return polyline
