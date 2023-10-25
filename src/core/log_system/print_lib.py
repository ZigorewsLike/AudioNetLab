import inspect
import os
from datetime import datetime

from src.global_constants import DEBUG


class ConsoleColors:
    DEBUG = '\033[92m'
    SIMPLE = '\033[0m'
    INFO = '\033[94m'
    ERROR = '\033[91m'
    BOLD = '\033[1m'
    ERROR_HEADER = f'{BOLD}{ERROR}'
    ERROR_BODY = f'{SIMPLE}{ERROR}'


def print_base(mode: str, text: any, module: str, colors: list) -> None:
    """
    Custom print. Example: [$mode] $module: $text

    :param colors: Color
    :param mode: DEBUG or ERROR
    :param text: Your print text
    :param module: module's name
    :return: None
    """
    print(f"{colors[0]}{datetime.now():%Y.%m.%d %H:%M:%S} [{mode}] {module}:{colors[1]}", *text)


def print_d(*text: any) -> None:
    """
    Debug print version

    :param text: Your print text
    :return: None
    """
    if DEBUG:
        current_frame = inspect.stack()[1]
        module = inspect.getmodule(current_frame[0])
        if module is not None:
            module_name = module.__name__
        else:
            module_name = os.path.basename(inspect.getfile(current_frame[0]))
        print_base("DEBUG", text, f"{module_name}|{current_frame.lineno} ",
                   [ConsoleColors.DEBUG, ConsoleColors.SIMPLE])


def print_i(*text: any) -> None:
    """
    Info print version

    :param text: Your print text
    :return: None
    """
    current_frame = inspect.stack()[1]
    module = inspect.getmodule(current_frame[0])
    if module is not None:
        module_name = module.__name__
    else:
        module_name = "UNKNOWN"
    print_base("INFO", text, f"{module_name}|{current_frame.lineno} ",
               [ConsoleColors.INFO, ConsoleColors.SIMPLE])


def log_i(*text: any) -> None:
    """
    Print for Users

    :param text: Your print text
    :return: None
    """
    print_base("INFO", text, "", [ConsoleColors.INFO, ConsoleColors.SIMPLE])


def print_e(*text: any) -> None:
    """
    'Error' print version

    :param text: Your print text
    :return: None
    """
    current_frame = inspect.stack()[1]
    module = inspect.getmodule(current_frame[0])
    if module is not None:
        module_name = module.__name__
    else:
        module_name = "UNKNOWN"
    print_base("ERROR", text, f"{module_name}:{current_frame.lineno} ",
               [ConsoleColors.ERROR_HEADER, ConsoleColors.ERROR_BODY])
