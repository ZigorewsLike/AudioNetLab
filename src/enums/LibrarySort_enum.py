from enum import Enum


class AlbumSort(str, Enum):
    """Order the album grid of the library tab is filled in."""
    ARTIST = "artist"  # Album artist, then year
    TITLE = "title"
    YEAR = "year"
    DATE_ADDED = "date_added"
    MANUAL = "manual"  # Order the user dragged the tiles into, Album.sort_index


class TrackSort(str, Enum):
    """Order the track table of the library tab is filled in."""
    TITLE = "title"
    ARTIST = "artist"
    ALBUM = "album"  # Album, then disc and track number, which is the playing order
    DURATION = "duration"
    YEAR = "year"
    DATE_ADDED = "date_added"
    LAST_OPENED = "last_opened"


class ArtistSort(str, Enum):
    """Order the artist grid of the library tab is filled in."""
    NAME = "name"  # Sort name, so "The Beatles" lands under B
    ALBUM_COUNT = "album_count"
