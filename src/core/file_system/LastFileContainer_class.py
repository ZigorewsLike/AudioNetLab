import os
import shutil
import datetime
import pickle

from src.global_constants import LAST_FILE_LIMIT, APP_ROAMING_DIR, LAST_FILE_FILENAME


class LastFileProp:
    def __init__(self, path, last_date, index=0):
        self.path: str = path
        self.last_date: datetime.datetime = last_date
        self.file_index: int = index

    def __str__(self):
        return f"{self.path}, {self.last_date}, {self.file_index}"

    def __eq__(self, other):
        return self.path == other.path


class LastFileContainer:
    def __init__(self):
        self.props: list = []
        self.max_row: int = LAST_FILE_LIMIT

    def __str__(self):
        return str([str(el) for el in self.props])

    def add(self, elem: LastFileProp):
        for i, item in enumerate(self.props):
            if elem == item:
                elem.file_index = item.file_index
                self.props.pop(i)
                break
        self.props.append(elem)
        if len(self.props) == 0:
            self.props.append(elem)
        if len(self.props) > self.max_row:
            self.props.pop(0)

        self.save_to_file()

    def delete(self, item: LastFileProp):
        self.props.remove(item)
        self.save_to_file()

    def save_to_file(self):
        with open(LAST_FILE_FILENAME, "wb") as f:
            pickle.dump(self, f)
        shutil.copy(LAST_FILE_FILENAME, os.path.join(APP_ROAMING_DIR, LAST_FILE_FILENAME))

    def get_last(self) -> LastFileProp:
        return self.props[len(self.props)-1]
