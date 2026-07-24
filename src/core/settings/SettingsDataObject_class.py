import configparser
from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, Dict, Tuple

from PyQt6.QtGui import QColor

from src.core.point_system import Point
from src.core.log_system import print_e
from src.global_constants import VERSION


@dataclass()
class SystemSettings:
    """Window geometry and application version stored in the ini file."""
    form_width: int
    form_height: int
    form_position: Point
    version: str


@dataclass()
class PlayerSettings:
    """Player state restored on the next start."""
    volume: int
    auto_play: bool
    graph_visible: bool


class SettingsDataObject:
    """Application settings backed by an ini file.

    Every dataclass becomes an ini section and every field becomes a key, so a new
    setting only needs to be added to the corresponding dataclass.
    """

    def __init__(self):
        """Create the settings with their default values.

        :returns: None.
        """
        self.system_settings = SystemSettings(form_width=1600, form_height=900, form_position=Point(-1.0, -1.0),
                                              version=f"{VERSION}")
        self.player_settings = PlayerSettings(volume=500, auto_play=False, graph_visible=True)

    def __repr__(self) -> str:
        """Describe the current settings.

        :returns: str - Text representation.
        """
        return f"SettingsDataObject({self.system_settings}, {self.player_settings})"

    @staticmethod
    def data_to_str(data: Any) -> str:
        """Serialise a setting value for the ini file.

        :param data: Value of any supported type.
        :returns: str - Text representation.
        """
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
        """Parse a setting value read from the ini file.

        :param data: Text representation.
        :param data_type: Target type taken from the dataclass field.
        :returns: The value converted to data_type.
        """
        if data_type is QColor:
            return QColor(data)
        elif data_type is Point:
            x, y = data.split(":")
            return Point(float(x), float(y))
        elif data_type is bool:
            return eval(data)
        return data_type(data)

    def save_to_ini(self, save_path: str) -> None:
        """Write every settings section to an ini file.

        :param save_path: Path to the ini file.
        :returns: None.
        """
        conf = configparser.ConfigParser()
        for class_field in [self.system_settings, self.player_settings]:
            conf.add_section(class_field.__class__.__name__)
            for data_field in fields(class_field):
                conf.set(class_field.__class__.__name__, data_field.name,
                         self.data_to_str(getattr(class_field, data_field.name)))
        with open(save_path, 'w', encoding='UTF-8') as f:
            conf.write(f)

    def load_from_ini(self, file: str) -> bool:
        """Read the ini file and apply the known keys, keeping defaults for the rest.

        :param file: Path to the ini file.
        :returns: True when the file was read without errors.
        """
        try:
            config = configparser.ConfigParser()
            config.read(file, encoding='UTF-8')
            # Owning dataclass and declared type per field name
            field_dict: Dict[str, Tuple[object, type]] = {}
            for class_field in [self.system_settings, self.player_settings]:
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
    s.save_to_ini('test_2.ini')