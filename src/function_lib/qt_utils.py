import os
from typing import Dict, Tuple

import numpy as np
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPixmap, QPolygonF
from PyQt6.QtWidgets import QLabel

# Cache of the scaled status markers, keyed by (paused, size)
_status_icon_cache: Dict[Tuple[bool, int], QPixmap] = {}

# Cache of the scaled delete markers, keyed by size
_delete_icon_cache: Dict[int, QPixmap] = {}


def style_section_header(label: QLabel, delta_pt: int = 2) -> None:
    """Style a label as a settings section header: bold and a couple of points larger.

    :param label: Label to restyle in place.
    :param delta_pt: Points added to the current font size.
    :returns: None.
    """
    font = label.font()
    base = font.pointSize()
    if base <= 0:
        base = 9
    font.setPointSize(base + delta_pt)
    font.setBold(True)
    label.setFont(font)


def status_icon_pixmap(paused: bool, size: int) -> QPixmap:
    """Load the play or pause marker shown on the track that is playing.

    Reads a dedicated icon file so the marker is drawn from an image rather than
    painted by hand.

    :param paused: True for the pause marker, False for the play marker.
    :param size: Edge length to scale the marker to.
    :returns: QPixmap - The scaled marker, may be null when no icon file exists.
    """
    key = (paused, size)
    cached = _status_icon_cache.get(key)
    if cached is not None:
        return cached
    pixmap = QPixmap("res/icons/track_paused.png" if paused else "res/icons/track_playing.png")
    if not pixmap.isNull():
        pixmap = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
    _status_icon_cache[key] = pixmap
    return pixmap


def delete_icon_pixmap(size: int) -> QPixmap:
    """Load the delete marker shown on a hovered track row.

    :param size: Edge length to scale the marker to.
    :returns: QPixmap - The scaled marker, may be null when no icon file exists.
    """
    cached = _delete_icon_cache.get(size)
    if cached is not None:
        return cached
    pixmap = QPixmap("res/icons/track_delete_icon_black.png")
    if not pixmap.isNull():
        pixmap = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
    _delete_icon_cache[size] = pixmap
    return pixmap


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
