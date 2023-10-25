import configparser
import re
import shutil
from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, List, Dict, Tuple

from PyQt6.QtGui import QColor

from src.core.point_system import Point
from src.core.log_system import print_e, print_d
from src.global_constants import VERSION


@dataclass()
class SystemSettings:
    form_width: int
    form_height: int
    form_position: Point
    last_file: str
    last_folder: str
    open_dir: str
    open_filename: str
    console_height: int
    version: str


class SettingsDataObject:
    def __init__(self):
        self.system_settings = SystemSettings(form_width=1600, form_height=900, form_position=Point(-1.0, -1.0),
                                              last_file="", last_folder="", open_dir="", open_filename="",
                                              console_height=206, version=f"{VERSION}")

    def __repr__(self) -> str:
        return f"SettingsDataObject({self.system_settings})"

    @staticmethod
    def data_to_str(data: Any) -> str:
        if isinstance(data, QColor):
            return data.name()
        elif isinstance(data, Enum):
            return data.name
        elif isinstance(data, Point):
            return f"{data.x}:{data.y}"
        else:
            return str(data)

    @staticmethod
    def data_from_str(data: str, data_type: type) -> Any:
        # future
        # if data_type is EnumClass:
        #     return data_type[data]  # noqa
        if data_type is QColor:
            return QColor(data)
        elif data_type is Point:
            x, y = data.split(":")
            return Point(float(x), float(y))
        elif data_type is bool:
            return eval(data)
        return data_type(data)

    def save_to_ini(self, save_path: str) -> None:
        conf = configparser.ConfigParser()
        for class_field in [self.system_settings]:
            conf.add_section(class_field.__class__.__name__)
            for data_field in fields(class_field):
                conf.set(class_field.__class__.__name__, data_field.name,
                         self.data_to_str(getattr(class_field, data_field.name)))
        with open(save_path, 'w', encoding='UTF-8') as f:
            conf.write(f)

    def load_from_ini(self, file: str) -> bool:
        try:
            config = configparser.ConfigParser()
            config.read(file, encoding='UTF-8')
            field_dict: Dict[str, Tuple[object, type]] = {}
            for class_field in [self.system_settings]:
                for data_field in fields(class_field):
                    field_dict[data_field.name] = (class_field, data_field.type)
            for each_section in config.sections():
                for each_key, each_val in config.items(each_section):
                    if each_key in field_dict.keys():
                        class_filed, class_type = field_dict[each_key]
                        new_value = self.data_from_str(each_val, class_type)
                        setattr(class_filed, each_key, new_value)
            return True
        except Exception as e:
            print_e("Fail load ini settings", e)
            return False


if __name__ == '__main__':
    s = SettingsDataObject()
    # s.load_from_ini('../../config.ini')
    # s.load_from_ini('test.ini')
    s.save_to_ini('test_2.ini')
