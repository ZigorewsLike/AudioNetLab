from typing import Dict, List, Optional

import numpy as np

from src.enums import ProfileDataType


class ProfileDrawData:
    def __init__(self) -> None:
        self._module_draw_call_container: Dict[str, np.ndarray] = {}
        self._module_math_call_container: Dict[str, np.ndarray] = {}
        self.data_limiter: int = 30
        self.fps_mode: bool = False
        self.round_step: int = 4

    def add_time_to_dict(self, dict_obj: dict,  module: str, ms: float, ignore_zero: bool = True) -> None:
        if ignore_zero and ms == 0.0:
            return
        draw_call_list: Optional[np.ndarray] = dict_obj.get(module, None)
        if draw_call_list is None:
            draw_call_list = np.array([ms])
        else:
            draw_call_list = np.append(draw_call_list, ms)
        dict_obj[module] = draw_call_list[max(0, draw_call_list.size - self.data_limiter):]

    def add_time(self, module: str, ms: float,  profile_data_type: ProfileDataType, ignore_zero: bool = True) -> None:
        if profile_data_type is ProfileDataType.DRAW_CALL:
            self.add_time_to_dict(self._module_draw_call_container, module, ms, ignore_zero)
        elif profile_data_type is ProfileDataType.MATH_CALL:
            self.add_time_to_dict(self._module_math_call_container, module, ms, ignore_zero)

    def get_modules(self, profile_data_type: ProfileDataType) -> list:
        if profile_data_type is ProfileDataType.DRAW_CALL:
            return list(self._module_draw_call_container.keys())
        elif profile_data_type is ProfileDataType.MATH_CALL:
            return list(self._module_math_call_container.keys())
        return []

    def get_time_list(self, module: str, profile_data_type: ProfileDataType) -> np.ndarray:
        if profile_data_type is ProfileDataType.DRAW_CALL:
            return self._module_draw_call_container.get(module, np.array([]))
        elif profile_data_type is ProfileDataType.MATH_CALL:
            return self._module_math_call_container.get(module, np.array([]))
        return np.array([])

    # region Get data from array (for Qt)
    def get_data_value(self, value) -> float | str:
        if self.fps_mode:
            if value != 0:
                return round(1000 / value)
            return "inf"
        return value

    def get_mean_time(self, module: str, profile_data_type: ProfileDataType) -> float | str:
        mean = round(self.get_time_list(module, profile_data_type).mean(), self.round_step)
        return self.get_data_value(mean)

    def get_max_time(self, module: str, profile_data_type: ProfileDataType) -> float | str:
        data_max = round(self.get_time_list(module, profile_data_type).max(), self.round_step)
        return self.get_data_value(data_max)

    def get_min_time(self, module: str, profile_data_type: ProfileDataType) -> float | str:
        data_min = round(self.get_time_list(module, profile_data_type).min(), self.round_step)
        return self.get_data_value(data_min)
    # endregion

