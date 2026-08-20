from enum import Enum


class ScanStage(str, Enum):
    """Stage the library scanner reports its progress for."""
    WALK = "walk"  # Listing the folders, the total is not known yet
    READ = "read"  # Reading tags and covers, writing them in batches
    FINALIZE = "finalize"  # Marking the files that disappeared
    DONE = "done"
