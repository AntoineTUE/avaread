"""Avaread is a package that provides methods for reading Avantes AvaSoft files.

It supports both 'regular' files, as well as STR (Store-to-RAM) files.
"""

__all__ = ["AVSFile", "STRFile", "open_file"]

from .reader import read_file

from ._version import __version__, __version_tuple__, version, version_tuple
