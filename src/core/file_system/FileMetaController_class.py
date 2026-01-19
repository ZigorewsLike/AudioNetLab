import os
import pickle
from typing import Optional

import numpy as np
import mutagen
from PyQt6.QtGui import QImage
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

from src.core.log_system import print_e
from src.enums import RegistryFileName
from src.global_constants import PATH_TO_LAST_REGISTRY


class FileMetaController:
    def __init__(self):
        self.track_meta: Optional[dict] = None
        self.track_meta_image_bytes: Optional[bytes] = None

    def read_track_file(self, path: str) -> Optional[dict]:
        self.track_meta_image_bytes = None
        _, file_extension = os.path.splitext(path)
        try:
            if file_extension.lower() == '.flac':
                audio = FLAC(path)
                self.track_meta_image_bytes = audio.pictures[0].data
            elif file_extension.lower() == '.mp3':
                audio = MP3(path)
                apic = audio.tags.get("APIC:", None)
                if apic:
                    self.track_meta_image_bytes = apic.data
            else:
                raise ValueError
        except Exception as e:
            print_e("Meta read error", e)
            audio = mutagen.File(path)
        if audio is None:
            print_e(f'Open file error. {path}')
        self.track_meta = audio

        return self.track_meta

    @staticmethod
    def get_registry_path(track_id: int) -> str:
        return f"{PATH_TO_LAST_REGISTRY}/{track_id}"

    def save_meta_in_registry(self, track_id: int):
        path_to_reg_folder: str = self.get_registry_path(track_id)
        os.makedirs(path_to_reg_folder, exist_ok=True)
        if self.track_meta_image_bytes is not None:
            with open(f"{path_to_reg_folder}/{RegistryFileName.PREVIEW}", "wb") as binary_file:
                binary_file.write(self.track_meta_image_bytes)

        if self.track_meta:
            with open(f"{path_to_reg_folder}/{RegistryFileName.TRACK_META}", "wb") as p_file:
                pickle.dump(self.track_meta, p_file)

    def get_preview_cover(self, track_id: int) -> Optional[QImage]:
        path_to_reg_folder: str = self.get_registry_path(track_id)
        if os.path.exists(f"{path_to_reg_folder}/{RegistryFileName.PREVIEW}"):
            with open(f"{path_to_reg_folder}/{RegistryFileName.PREVIEW}", "rb") as binary_file:
                img = QImage()
                img.loadFromData(binary_file.read())
                return img
        return None

    def get_track_meta(self, track_id: int) -> Optional[dict]:
        path_to_reg_folder: str = self.get_registry_path(track_id)
        if os.path.exists(f"{path_to_reg_folder}/{RegistryFileName.TRACK_META}"):
            with open(f"{path_to_reg_folder}/{RegistryFileName.TRACK_META}", "rb") as binary_file:
                return pickle.load(binary_file)
        return None

    def get_track_librosa_data(self, track_id: int) -> Optional[dict]:
        path_to_reg_folder: str = self.get_registry_path(track_id)
        if os.path.exists(f"{path_to_reg_folder}/{RegistryFileName.LIBROSA_DATA}"):
            return np.load(f"{path_to_reg_folder}/{RegistryFileName.LIBROSA_DATA}")
        return None

    def save_track_librosa_data(self, track_id: int, data: np.ndarray) -> None:
        path_to_reg_folder: str = self.get_registry_path(track_id)
        np.save(f"{path_to_reg_folder}/{RegistryFileName.LIBROSA_DATA}", data)

    def get_track_transcription(self, track_id: int) -> Optional[dict]:
        path_to_reg_folder: str = self.get_registry_path(track_id)
        if os.path.exists(f"{path_to_reg_folder}/{RegistryFileName.TRANSCRIPTION}"):
            with open(f"{path_to_reg_folder}/{RegistryFileName.TRANSCRIPTION}", "rb") as binary_file:
                return pickle.load(binary_file)
        return None

    def save_track_transcription(self, track_id: int, data: dict) -> None:
        path_to_reg_folder: str = self.get_registry_path(track_id)
        with open(f"{path_to_reg_folder}/{RegistryFileName.TRANSCRIPTION}", "wb") as p_file:
            pickle.dump(data, p_file)
