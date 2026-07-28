import os
import pickle
import shutil
from typing import Optional

import numpy as np
import mutagen
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QImage
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

from .tag_reader import cover_bytes_from_audio, find_folder_cover
from src.core.log_system import print_e
from src.enums import RegistryFileName
from src.global_constants import PATH_TO_LAST_REGISTRY


class FileMetaController:
    """Per track registry stored in data/registry/<track_id>.

    Keeps everything that is expensive to recompute: the tag dump, the cached
    librosa feature vectors used by the genre classifier and the lyrics.
    """

    def __init__(self):
        """Create the controller.

        :returns: None.
        """
        self.track_meta: Optional[dict] = None
        self.find_image_on_disk = True  # Look for a cover next to the file when the tags have none

    def read_track_file(self, path: str) -> Optional[dict]:
        """Read the tags of an audio file.

        :param path: Path to the audio file.
        :returns: Mutagen tag object, None when the file cannot be parsed.
        """
        _, file_extension = os.path.splitext(path)
        try:
            if file_extension.lower() == '.flac':
                audio = FLAC(path)
            elif file_extension.lower() == '.mp3':
                audio = MP3(path)
            else:
                raise ValueError
        except Exception as e:
            print_e("Meta read error", e)
            audio = mutagen.File(path)  # Let mutagen guess the format
        if audio is None:
            print_e(f'Open file error. {path}')
        self.track_meta = audio

        return self.track_meta

    @staticmethod
    def get_registry_path(track_id: int) -> str:
        """Build the registry folder path of a track.

        :param track_id: Track id.
        :returns: str - Path to the registry folder.
        """
        return f"{PATH_TO_LAST_REGISTRY}/{track_id}"

    def save_meta_in_registry(self, track_id: int):
        """Store the last read tags in the track registry.

        :param track_id: Track id.
        :returns: None.
        """
        path_to_reg_folder: str = self.get_registry_path(track_id)
        os.makedirs(path_to_reg_folder, exist_ok=True)

        if self.track_meta:
            with open(f"{path_to_reg_folder}/{RegistryFileName.TRACK_META}", "wb") as p_file:
                pickle.dump(self.track_meta, p_file)

    def get_preview_cover(self, track_id: int, file_path: str = None,
                          meta: Optional[dict] = None) -> Optional[QImage]:
        """Get the track cover from the tags, or from an image next to the file.

        Both lookups are delegated: the picture frames to cover_bytes_from_audio and
        the image on disk to find_folder_cover, so this agrees with what the library
        scanner stored for the same track instead of applying its own rules.

        :param track_id: Track id.
        :param file_path: Path to the audio file, enables the search on disk.
        :param meta: Already read tags, avoids a second registry read when the caller has them.
        :returns: QImage - Cover image, None when nothing was found.
        """
        if meta is None:
            meta = self.get_track_meta(track_id)
        image_bytes = cover_bytes_from_audio(meta)
        if image_bytes is not None:
            image = QImage()
            if image.loadFromData(image_bytes):
                return image

        if file_path and self.find_image_on_disk:
            try:
                image_path = find_folder_cover(os.path.dirname(file_path))
                if image_path:
                    # Crop to a centred square, the player draws the cover in a square
                    image = QImage(image_path)
                    if image.isNull():
                        return None
                    side = min(image.width(), image.height())
                    return image.copy(QRect((image.width() - side) // 2,
                                            (image.height() - side) // 2, side, side))
            except Exception as e:
                print_e(f"[{track_id}]: Preview from disk read error", e)
        return None

    def get_track_meta(self, track_id: int) -> Optional[dict]:
        """Read the stored tags of a track.

        :param track_id: Track id.
        :returns: Tag object, None when the registry has none.
        """
        path_to_reg_folder: str = self.get_registry_path(track_id)
        if os.path.exists(f"{path_to_reg_folder}/{RegistryFileName.TRACK_META}"):
            with open(f"{path_to_reg_folder}/{RegistryFileName.TRACK_META}", "rb") as binary_file:
                return pickle.load(binary_file)
        return None

    def get_track_librosa_data(self, track_id: int) -> Optional[dict]:
        """Read the cached feature vectors of the genre classifier.

        :param track_id: Track id.
        :returns: numpy array of features, None when the track has not been analysed yet.
        """
        path_to_reg_folder: str = self.get_registry_path(track_id)
        if os.path.exists(f"{path_to_reg_folder}/{RegistryFileName.LIBROSA_DATA}"):
            return np.load(f"{path_to_reg_folder}/{RegistryFileName.LIBROSA_DATA}")
        return None

    def save_track_librosa_data(self, track_id: int, data: np.ndarray) -> None:
        """Cache the feature vectors so the next prediction skips the extraction.

        :param track_id: Track id.
        :param data: Feature array, one row per fragment.
        :returns: None.
        """
        path_to_reg_folder: str = self.get_registry_path(track_id)
        np.save(f"{path_to_reg_folder}/{RegistryFileName.LIBROSA_DATA}", data)

    def get_track_transcription(self, track_id: int) -> Optional[dict]:
        """Read the stored lyrics of a track.

        :param track_id: Track id.
        :returns: dict - Lyrics with segments, None when there are none.
        """
        path_to_reg_folder: str = self.get_registry_path(track_id)
        if os.path.exists(f"{path_to_reg_folder}/{RegistryFileName.TRANSCRIPTION}"):
            with open(f"{path_to_reg_folder}/{RegistryFileName.TRANSCRIPTION}", "rb") as binary_file:
                return pickle.load(binary_file)
        return None

    def save_track_transcription(self, track_id: int, data: dict) -> None:
        """Store the lyrics of a track.

        :param track_id: Track id.
        :param data: Lyrics with segments.
        :returns: None.
        """
        path_to_reg_folder: str = self.get_registry_path(track_id)
        with open(f"{path_to_reg_folder}/{RegistryFileName.TRANSCRIPTION}", "wb") as p_file:
            pickle.dump(data, p_file)

    def get_lyrics(self, track_id: int) -> Optional[str]:
        """Extract the lyrics from the FLAC tags of a track.

        :param track_id: Track id.
        :returns: str - Lyrics text, None when no lyrics tag is present.
        """
        meta = self.get_track_meta(track_id)
        if isinstance(meta, FLAC):
            for k in ["LYRICS", "UNSYNCEDLYRICS", "LYRIC", "LYRICS:DESCRIPTION"]:
                if k in meta:
                    return ';'.join(meta[k])
        return None

    def delete_track(self, track_id: int) -> None:
        """Drop the registry folder of a track, if it has one.

        A track imported by the library scanner keeps its tags in the database and has
        no registry folder until it is opened, so deleting one that was never opened
        must not fail on the missing folder.

        :param track_id: Track id.
        :returns: None.
        """
        path_to_reg_folder: str = self.get_registry_path(track_id)
        shutil.rmtree(path_to_reg_folder, ignore_errors=True)