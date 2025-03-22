from src.core.log_system.print_lib import print_traceback, print_d
from src.global_constants import PROFILE

try:
    if not PROFILE:
        raise ValueError
    from line_profiler import profile
except Exception as ie:
    print_d("PROFILE mode is OFF")

    def profile(func):
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
        return wrapper
