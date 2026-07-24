import os
import re
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

import mutagen

from src.core.log_system import print_e
from src.global_constants import COVER_FILE_EXTENSIONS, COVER_FILE_NAMES

# "3/12" and "3 of 12" both mean track three, the total is stored separately
_NUMBER_RE = re.compile(r"^\s*(\d+)")
# A date tag can be a bare year, a full date or a range, only the first year matters
_YEAR_RE = re.compile(r"(\d{4})")

# region FLAC fast path
_FLAC_MAGIC = b"fLaC"
_BLOCK_STREAMINFO = 0
_BLOCK_VORBIS_COMMENT = 4
_MAX_BLOCKS = 128  # A real file has a handful, a larger count means a broken header
_MAX_COMMENT_BLOCK = 1 << 20  # Refuse to read an absurd comment block into memory
_MAX_COMMENTS = 4096
_ID3_MAGIC = b"ID3"
_ID3_HEADER_SIZE = 10
_ID3_FOOTER_FLAG = 0x10
# endregion


def _skip_id3(handle) -> bool:
    """Move an open file past a leading ID3v2 tag, if it has one.

    Some rippers write an ID3 header in front of a FLAC stream. Nothing in it is
    needed, the Vorbis comments behind it are authoritative.

    :param handle: File opened for binary reading, positioned at the start.
    :returns: bool - True when the file is positioned at the FLAC magic.
    """
    header = handle.read(_ID3_HEADER_SIZE)
    if len(header) < _ID3_HEADER_SIZE:
        return False
    if header[:3] != _ID3_MAGIC:
        handle.seek(0)
        return handle.read(4) == _FLAC_MAGIC

    # The size is stored as four synchsafe bytes, seven usable bits each
    size = 0
    for byte in header[6:10]:
        if byte & 0x80:
            return False  # Not a valid synchsafe integer, let mutagen deal with it
        size = (size << 7) | byte
    if header[5] & _ID3_FOOTER_FLAG:
        size += _ID3_HEADER_SIZE
    handle.seek(_ID3_HEADER_SIZE + size)
    return handle.read(4) == _FLAC_MAGIC


class TrackTags(NamedTuple):
    """Everything the library needs out of one audio file.

    Read with a single file open. The cover is deliberately absent: decoding it costs
    more than all the other fields together and is only worth doing once per album.
    """
    title: Optional[str]
    artist: Optional[str]
    album_artist: Optional[str]
    album: Optional[str]
    track_no: Optional[int]
    disc_no: Optional[int]
    year: Optional[int]
    genre: Optional[str]
    duration: Optional[float]
    bitrate: Optional[int]
    sample_rate: Optional[int]
    channels: Optional[int]


def _first(tags: Any, *keys: str) -> Optional[str]:
    """Read the first non empty value of the first key that is present.

    Tag values are lists in mutagen, and a file can carry the same information under
    several names depending on who wrote it.

    :param tags: Tag mapping of an opened file, may be None.
    :param keys: Key names to try in order.
    :returns: str - Value, None when no key holds anything.
    """
    if not tags:
        return None
    for key in keys:
        try:
            value = tags.get(key)
        except (KeyError, ValueError):
            continue  # EasyID3 raises on keys it does not know
        if not value:
            continue
        if isinstance(value, (list, tuple)):
            value = next((v for v in value if str(v).strip()), None)
            if value is None:
                continue
        text = str(value).strip()
        if text:
            return text
    return None


def _to_int(value: Optional[str]) -> Optional[int]:
    """Read the leading integer of a tag value.

    :param value: Raw tag value such as "3", "3/12" or "3 of 12".
    :returns: int - The number, None when there is none.
    """
    if not value:
        return None
    match = _NUMBER_RE.match(str(value))
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _to_year(value: Optional[str]) -> Optional[int]:
    """Read the year out of a date tag.

    :param value: Raw date tag such as "1987", "1987-05-01" or "1987/1990".
    :returns: int - Year, None when the tag holds no four digit number.
    """
    if not value:
        return None
    match = _YEAR_RE.search(str(value))
    if match is None:
        return None
    year = int(match.group(1))
    return year if 1000 <= year <= 2999 else None


def _parse_vorbis_comment(data: bytes) -> Dict[str, List[str]]:
    """Parse a Vorbis comment block into a mapping of lowercase keys to values.

    :param data: Raw contents of the comment block.
    :returns: Dict[str, List[str]] - Values per key, a key may carry several.
    """
    result: Dict[str, List[str]] = {}
    size = len(data)
    if size < 8:
        return result
    offset = 4 + int.from_bytes(data[0:4], "little")  # Skip the vendor string
    if offset + 4 > size:
        return result
    count = int.from_bytes(data[offset:offset + 4], "little")
    offset += 4
    for _ in range(min(count, _MAX_COMMENTS)):
        if offset + 4 > size:
            break
        length = int.from_bytes(data[offset:offset + 4], "little")
        offset += 4
        if length > size - offset:
            break
        entry = data[offset:offset + length].decode("utf-8", "replace")
        offset += length
        key, separator, value = entry.partition("=")
        if separator:
            result.setdefault(key.strip().lower(), []).append(value)
    return result


def read_flac_tags_fast(path: str, file_size: Optional[int] = None) -> Optional[TrackTags]:
    """Read FLAC tags without pulling the embedded cover off the disk.

    This exists because mutagen loads every metadata block, and a FLAC with artwork
    carries a few hundred kilobytes of it. Reading that for every track only to decode
    one cover per album turns an import into a transfer of the whole artwork of the
    collection, which on a mechanical drive is what the import time is made of.

    Only STREAMINFO and the Vorbis comments are read here, everything else is seeked
    past, so a track costs a few kilobytes instead of a few hundred. Anything
    unexpected returns None and the caller falls back to mutagen.

    :param path: Path to the FLAC file.
    :param file_size: Size of the file, saves a stat when the caller knows it.
    :returns: TrackTags - Tags of the file, None when it is not a plain FLAC.
    """
    try:
        with open(path, "rb") as handle:
            if not _skip_id3(handle):
                return None  # Could be FLAC in an Ogg container, mutagen handles that

            sample_rate: Optional[int] = None
            channels: Optional[int] = None
            total_samples: int = 0
            comments: Dict[str, List[str]] = {}

            for _ in range(_MAX_BLOCKS):
                header = handle.read(4)
                if len(header) < 4:
                    return None
                is_last = bool(header[0] & 0x80)
                block_type = header[0] & 0x7F
                length = int.from_bytes(header[1:4], "big")

                if block_type == _BLOCK_STREAMINFO:
                    data = handle.read(length)
                    if len(data) < 18:
                        return None
                    # Bytes 10..17 pack sample rate (20), channels (3),
                    # bits per sample (5) and the total sample count (36)
                    packed = int.from_bytes(data[10:18], "big")
                    sample_rate = packed >> 44
                    channels = ((packed >> 41) & 0x07) + 1
                    total_samples = packed & ((1 << 36) - 1)
                elif block_type == _BLOCK_VORBIS_COMMENT:
                    if length > _MAX_COMMENT_BLOCK:
                        return None
                    comments = _parse_vorbis_comment(handle.read(length))
                else:
                    handle.seek(length, os.SEEK_CUR)  # PICTURE never leaves the disk

                if is_last:
                    break
            else:
                return None  # Absurd block count, let mutagen decide

            if not sample_rate:
                return None

            duration = round(total_samples / sample_rate, 3) if total_samples else None
            if file_size is None:
                file_size = os.path.getsize(path)
            # Everything read so far is metadata, the audio starts here. Measuring the
            # bitrate over the whole file would inflate it by the size of the artwork.
            audio_bytes = max(0, file_size - handle.tell())
            bitrate = int(audio_bytes * 8 / duration) if duration else None

            return _build_tags(comments, duration=duration, bitrate=bitrate,
                               sample_rate=sample_rate, channels=channels)
    except (OSError, ValueError):
        return None


def _build_tags(tags: Any, duration: Optional[float], bitrate: Optional[int],
                sample_rate: Optional[int], channels: Optional[int]) -> TrackTags:
    """Assemble the record from a tag mapping and the stream properties.

    :param tags: Tag mapping, keyed the way mutagen easy mode keys it.
    :param duration: Length in seconds.
    :param bitrate: Bits per second.
    :param sample_rate: Samples per second.
    :param channels: Channel count.
    :returns: TrackTags - Tags of the file.
    """
    return TrackTags(
        title=_first(tags, "title"),
        artist=_first(tags, "artist", "performer"),
        album_artist=_first(tags, "albumartist", "album artist", "albumartistsort"),
        album=_first(tags, "album"),
        track_no=_to_int(_first(tags, "tracknumber", "track")),
        disc_no=_to_int(_first(tags, "discnumber", "disc")),
        year=_to_year(_first(tags, "date", "originaldate", "year")),
        genre=_first(tags, "genre"),
        duration=duration,
        bitrate=bitrate,
        sample_rate=sample_rate,
        channels=channels,
    )


def read_tags(path: str, file_size: Optional[int] = None) -> Optional[TrackTags]:
    """Read the tags and the stream properties of an audio file.

    FLAC takes a fast path that skips the artwork, see read_flac_tags_fast. Everything
    else is opened once in mutagen easy mode, which maps the format specific frame
    names onto one set of keys, so ID3 and RIFF tags are read by the same code.

    :param path: Path to the audio file.
    :param file_size: Size of the file, saves a stat when the caller knows it.
    :returns: TrackTags - Tags of the file, None when it cannot be parsed.
    """
    if os.path.splitext(path)[1].lower() == ".flac":
        fast = read_flac_tags_fast(path, file_size)
        if fast is not None:
            return fast

    try:
        audio = mutagen.File(path, easy=True)
    except Exception as e:
        print_e(f"Tag read error: {path}", e)
        return None
    if audio is None:
        return None

    info = getattr(audio, "info", None)
    length = getattr(info, "length", None) if info is not None else None
    return _build_tags(
        audio.tags,
        duration=round(float(length), 3) if length else None,
        bitrate=getattr(info, "bitrate", None) if info is not None else None,
        sample_rate=getattr(info, "sample_rate", None) if info is not None else None,
        channels=getattr(info, "channels", None) if info is not None else None,
    )


def cover_bytes_from_audio(audio: Any) -> Optional[bytes]:
    """Pull the embedded picture out of an already opened mutagen object.

    Kept separate from the file reading so the track registry, which stores the
    mutagen object itself, extracts a cover with exactly the same rules as the
    library scanner, which extracts it from the file.

    :param audio: Mutagen object, opened or restored from the registry.
    :returns: bytes - Encoded image, None when there is no picture.
    """
    if audio is None:
        return None
    try:
        # FLAC keeps pictures in their own metadata blocks
        pictures = getattr(audio, "pictures", None)
        if pictures:
            return bytes(pictures[0].data)

        tags = getattr(audio, "tags", None)
        if not tags:
            return None

        # ID3 stores every picture under an APIC key suffixed with its description
        for key in getattr(tags, "keys", lambda: [])():
            if str(key).startswith("APIC"):
                data = getattr(tags[key], "data", None)
                if data:
                    return bytes(data)

        # MP4 and, through mutagen, a few other containers
        covr = tags.get("covr") if hasattr(tags, "get") else None
        if covr:
            return bytes(covr[0])
    except Exception as e:
        print_e("Cover extract error", e)
    return None


def read_embedded_cover(path: str) -> Optional[bytes]:
    """Read the cover image embedded in the tags of an audio file.

    Called once per album rather than once per track, because this is the expensive
    read: it opens the file without the easy mapping, which is the only way to reach
    the picture frames and pulls the artwork off the disk.

    :param path: Path to the audio file.
    :returns: bytes - Encoded image, None when the file carries no picture.
    """
    try:
        audio = mutagen.File(path)
    except Exception as e:
        print_e(f"Cover read error: {path}", e)
        return None
    return cover_bytes_from_audio(audio)


def find_folder_cover(folder: str) -> Optional[str]:
    """Find the image file that stands in for a cover in an album folder.

    Preferred names come first, any other image in the folder is the last resort.

    :param folder: Folder holding the audio files.
    :returns: str - Path to the image, None when the folder has none.
    """
    try:
        entries = [entry for entry in os.scandir(folder) if entry.is_file()]
    except OSError:
        return None

    images: Dict[str, str] = {}
    for entry in entries:
        stem, extension = os.path.splitext(entry.name)
        if extension.lower() in COVER_FILE_EXTENSIONS:
            images[stem.lower()] = entry.path

    for name in COVER_FILE_NAMES:
        for stem, image_path in images.items():
            if stem == name or stem.startswith(name):
                return image_path
    if images:
        return sorted(images.values())[0]
    return None


def read_folder_cover(folder: str) -> Optional[bytes]:
    """Read the cover image lying next to the audio files of an album.

    :param folder: Folder holding the audio files.
    :returns: bytes - Encoded image, None when the folder has none.
    """
    image_path = find_folder_cover(folder)
    if image_path is None:
        return None
    try:
        return Path(image_path).read_bytes()
    except OSError as e:
        print_e(f"Folder cover read error: {image_path}", e)
        return None


def title_from_path(path: str) -> str:
    """Build a readable title out of a file name, for files without a title tag.

    :param path: Path to the audio file.
    :returns: str - Title.
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    # Drop a leading track number the way "03 - Bones" or "03. Bones" writes it
    cleaned = re.sub(r"^\s*\d{1,3}\s*[-._)]?\s+", "", stem)
    return cleaned.strip() or stem


def iter_audio_files(folder: str, extensions: List[str], recursive: bool = True):
    """Walk a folder and yield the audio files it holds.

    Uses scandir rather than walk so the size and the modification time come from the
    directory entry the operating system already returned, without a stat per file.

    :param folder: Folder to walk.
    :param extensions: Lowercase extensions to keep, including the dot.
    :param recursive: Descend into subfolders.
    :returns: Iterator of (path, size, mtime) tuples.
    """
    stack = [folder]
    extension_set = set(extensions)
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError as e:
            print_e(f"Folder read error: {current}", e)
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    if recursive:
                        stack.append(entry.path)
                    continue
                if os.path.splitext(entry.name)[1].lower() not in extension_set:
                    continue
                stat = entry.stat()
                yield entry.path, stat.st_size, stat.st_mtime
            except OSError:
                continue  # The file disappeared between the listing and the stat
