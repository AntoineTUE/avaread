"""A module containing the actual logic for reading Avantes AvaSoft files."""

import os
from pathlib import Path
from datetime import datetime
import numpy as np
from ctypes import sizeof, POINTER, cast, Array, c_char, c_double, c_long, c_byte
from enum import IntEnum
from io import BufferedReader
import struct
from typing import TYPE_CHECKING

from avaread.AvaTypes import MappableStructure, AVSInfoBlock, AVSPreamble, STRPreamble, STRInfoBlock


from numpy.typing import NDArray


class AvaReadException(BaseException):
    """Exception thrown when there are problems when reading a file."""


def _extract_datetime(timestamp: int):
    """Extract a `datetime` object from a provided timestamp."""
    year = timestamp >> 20
    month = (timestamp >> 16) % 16
    day = (timestamp >> 11) % 32
    hour = (timestamp >> 6) % 32
    minute = timestamp % 64
    return datetime(year=year, month=month, day=day, hour=hour, minute=minute)


class StructMapping:
    """Object to map the contents of a C structure to more python-native objects.

    Enum values will be mapped to the appropriate enums (if set in the [`MappableStructure._map`][(p).AvaTypes.MappableStructure._map] attribute), while numeric arrays will use numpy arrays, and `char` arrays become strings.

    This mapping will happen each time an attribute is accessed, which means it will reflect changes made to the content of the underlying struct.

    You should not use this class to modify attributes, rather you should update the underlying struct(s) itself.

    The main purpose is to map (nested) structures to types that are easier to work with and represent in Python.
    """

    def __init__(self, struct: MappableStructure):
        """Create a shallow proxy object for a [`MappableStructure`][(p).AvaTypes.MappableStructure] that maps the contents to python native types."""
        self._name = struct.__class__.__name__
        self.fields = [n for n, _ in struct._fields_]
        self.struct = struct

    def __getattr__(self, name: str):
        """Retrieve the value of a field from the underlying [`MappableStructure`][(p).AvaTypes.MappableStructure] that is mapped by this instance.

        If a field is a Structure itself, it will be recursively mapped as well using another `StructMapping`, which allows attribute traversal down the hierarchy.

        Example: `object.attribute.subattribute.field`.

        If an attribute/field does not exists, raises an `AttributeError`.

        Otherwise maps the field to a Python native type (from C compatible type using ctypes).

        This mapping occurs every time the attribute is accessed (i.e. it is not cached), and thus should be avoided if it is expensive or happens frequently.

        Args:
            name:   A string that specifies the name of the field to lookup and map.

        Raises:
            AttributeError
        """
        if name in (field for field, _ in self.struct._fields_):
            ctype = next((_type for field, _type in self.struct._fields_ if field == name))
            _value = getattr(self.struct, name)
            if issubclass(ctype, Array):
                if ctype._type_ is c_char:
                    value = _value.decode("utf-8", errors="ignore")
                else:
                    dt = np.dtype(type(_value[0]))
                    value = np.ctypeslib.as_array(_value).astype(dt)
                    assert value.dtype == dt
            elif name in self.struct._map:
                value = self.struct._map[name](_value)
            elif isinstance(_value, MappableStructure):
                value = StructMapping(_value)
            else:
                value = _value
        else:
            raise AttributeError(f"{name} is not a valid field")
        return value

    def __repr__(self):
        """Returns string representation of the [StructMapping][(c)], showing which type of struct is being mapped."""
        return f"Mapped{self._name}({','.join(self.fields)})"

    def print(self, prefix: str = ""):
        """Print the contents of the underlying struct by traversing it's hierarchy.

        Args:
            prefix:   String to use when creating the full name of a field., mainly used for resolving field names in nested hierarchies. Default: ""
        """
        for name, _dtype in self.struct._fields_:
            full_name = f"{prefix}.{name}".strip(".")
            prop = getattr(self, name)
            if isinstance(prop, StructMapping):
                prop.print(prefix=full_name)
            elif isinstance(prop, IntEnum):
                print(full_name, prop.__repr__())
            else:
                print(full_name, prop)


class AVSChannel:
    """Represents data and metadata header of an Avantes spectrometer channel.

    Each [`AVSFile`][(m).AVSFile] can stores one or more blocks containing this information, one for each channel/spectrometer.
    """

    PADDING = 10
    """A padding of 10 bytes between consecutive blocks of channel data."""

    def __init__(self, header: AVSInfoBlock, data: NDArray[np.float32]):
        """Instantiate a `AVSChannel` from a header (which contain metadata) and data.

        To access the data you can use the following attibutes:
        [`scope`][..] corresponds to the raw signal, [`dark`][..] to the associated background signal, and [`ref`][..] to a reference signal.

        In addition, the [`data`][..] attribute gives you the array of all these signals together.

        Arguments:
            header:     A C Structure containing channel-specific metadata.
            data:       A 2D array with columns in the order [`wavelength`,`scope`,`dark`,`reference`]


        """
        self._mapping = StructMapping(header)
        self.data = data

    def __getattr__(self, name):
        """Lookup metadata via attribute access.

        The [`_mapping`][..] attribute itself is a [StructMapping][(m).StructMapping] that allows accessing Structure fields as Python-native types.

        Supports traversing the header hierarcy via attribute access.

        Example: `AVSChannel.Measurement.StartPixel`
        """
        return getattr(self._mapping, name)

    def __repr__(self):
        """Representation of the [AVSChannel][(c)] as a string.

        Shows characteristic information such as serial number, wavelength range, exposure time and pixel count.
        """
        return f"AVSChannel(SN={self.ID.SerialNumber}, λ=({self.data[0, 0]:.1f},{self.data[-1, 0]:.1f}), exposure={self.Measurement.IntegrationTime:.3g} ms, Pixels={len(self)})"

    def __len__(self):
        """The length of the channel, i.e. the number of active pixels."""
        return self.Measurement.StopPixel - self.Measurement.StartPixel + 1

    @classmethod
    def from_buffer(cls, buffer, offset=0):
        """Read the binary data for a channel from an opened file handle.

        Each block of binary data has an empty padding of 3779 bytes it seems, plus [`PADDING`][..], between each channel binary block.
        """
        startBlock = buffer.tell()
        header = AVSInfoBlock()
        buffer.seek(offset, os.SEEK_CUR)
        buffer.readinto(header)
        num_pixels = header.Measurement.StopPixel - header.Measurement.StartPixel + 1
        # TODO: check if we need to account for start pixel being not the 0th pixel, thus needing to offset the read into the block.
        # It does not appear we read a pixel count, only start and stop pixels, thus don't know the size of the array/block.
        data = np.fromfile(buffer, dtype=np.float32, count=int(4 * num_pixels)).reshape(4, -1).T
        # endData = buffer.tell()
        # print(f"{endData=},{startBlock+header.blockLength-endData=}")
        # TODO: Check if this padding has a role, or is just padding
        buffer.seek(startBlock + header.blockLength + cls.PADDING)
        return AVSChannel(header, data)

    @property
    def serial(self):
        """The serial number of the spectrometer."""
        return self.ID.SerialNumber

    @property
    def date(self):
        """The date the spectrum was stored."""
        return _extract_datetime(self.Timestamp)

    @property
    def pixels(self):
        """Return the amount of active pixels of the acquisition.

        Note:
            This can be different from the total pixel count of the sensor if some pixels are deactivated.
        """
        return len(self)

    @property
    def exposure(self):
        """The exposure time used in milliseconds.

        Sometimes also called `integration time` of the sensor.
        """
        return self.Measurement.IntegrationTime

    @property
    def wavelength(self):
        """The wavelengths corresponding the the pixels of the detector of the spectrometer.

        The values of this pixel-to-wavelength mapping come from the calibration polynomial.
        """
        return self.data[:, 0]

    @property
    def scope(self):
        """The raw signal from the spectrometer, as stored in the file.

        Called the 'Scope' data (or RawScope) by Avantes.
        """
        return self.data[:, 1]

    @property
    def dark(self):
        """The 'dark' signal of the spectrometer, as stored in the file."""
        return self.data[:, 2]

    @property
    def ref(self):
        """The 'reference' signal of the spectrometer as stored in the file."""
        return self.data[:, 3]

    @property
    def signal(self):
        """The 'signal' of the spectrometer, computed from the raw signal minus dark signal."""
        return self.scope - self.dark


class AVSFile:
    """A file in Avantes `AVS` format, containing data from one or more channels."""

    def __init__(self, path: Path | str):
        """Read a AVS file from disk and create an object that can be used to easily acces the (meta)data.

        Each AVSFile will contain one or more [`AVSChannels`][(m).AVSChannel].

        These can be accessed via the [`channels`][(c).] attribute, which is a list of [`AVSChannel`][(m).AVSChannel]s.

        Alternatively, you can access the channels by index, like a list, or by the serial number of the channel, like a dict.

        Example:
        ```python
        file_name = pathlib.Path("./some_spectrum.raw8`) # a file with one or more channels

        data = AVSFile(file_name)

        for enumerate(spectrum) in data:
            print(spectrum)
            assert spectrum == data.channels[i] # access via the `channels` attribute is equivalent

        serial = data.channels[0].serial
        # all below ways of access are equivalent, you can access by index (like a list), or by key (like a dict)
        assert data[0] == data.channels[0] == data[serial]
        ```

        Args:
            path (Path|str): A file path to an `AVS` file.
        """
        self.path = Path(path).resolve()
        with self.path.open("rb") as fo:
            self.preamble = AVSPreamble()
            fo.readinto(self.preamble)
            if self.preamble.FileType != b"AVS":
                # Raise error when magic bytes mismatch
                raise AvaReadException(f"{self.path.name} is not a valid Avantes `AVS` file.")
            # TODO: maybe a version check?
            self.channels: list[AVSChannel] = [AVSChannel.from_buffer(fo) for _ in range(self.preamble.channels)]

    def __repr__(self):
        """Representation of the object."""
        return f"AVSFile(channels={[c.ID.SerialNumber for c in self.channels]})"

    def __getitem__(self, key):
        """Implement getting a channel by index or key, emulating behaviour of a list or dictionary.

        Along with `__len__` this makes the class iterable, i.e. one can iterate over channels contained within.
        """
        if isinstance(key, int):
            if key >= len(self.channels):
                raise IndexError(f"Index {key} is out of bounds for amount of channels ({len(self.channels)})")
            return self.channels[key]
        else:
            keys = [c.ID.SerialNumber for c in self.channels]
            if key not in keys:
                raise KeyError(f"Key {key} is not a valid channel serial number.")
            return self.channels[keys.index(key)]

    def __len__(self):
        """Return amount of channels contained in the file.

        Along with `__getitem__` this makes the class iterable, i.e. one can iterate over channels contained within.
        """
        return self.preamble.channels

    @property
    def name(self):
        """The name of the file."""
        return self.path.name

    @property
    def date(self):
        """The date that the file was stored on."""
        return self.channels[0].date


class STRFile:
    """A Store-to-RAM (STR) file.

    These STR files store multiple frames acquired by a single channel, i.e. a kinetic series, or a time-lapse.

    Instead of an [`AVSFile`][(m).], these files store data for a single channel, but multiple `frames` in sequence.

    The raw signals for all frames are stored in the [data][..] attribute as a numpy array.

    This array has the shape (pixels, frames), where pixels is the full size of the used CCD sensor.

    If the data was acquired with a smaller region on the sensor active, the inactive pixels will contain zeros.

    The attributes `scope`, `dark`, `ref`, and `signal` all conveniently return only the active part of the array.

    In addition, you can iterate over an `STRFile` to get the background-corrected data on a per-frame basis, or use access-by-index.

    Example:
    ```python
    file = pathlib.Path("./some_str_file.str")
    spectra = STRFile(file)

    for i,frame in enumerate(spectra):
        plt.plot(spectra.wavelength, frame, label=f"Frame: {i}")

    plt.legend()
    ```

    """

    def __init__(self, path: Path):
        """Read a STR file from disk and create an object that can be used to easily acces the (meta)data."""
        self.preamble = STRPreamble()
        self._header = STRInfoBlock()
        self._mapping = StructMapping(self._header)
        self.path = Path(path).resolve()
        with self.path.open("rb") as fo:
            fo.readinto(self.preamble)
            if self.preamble.FileType != b"STR":
                # Raise error when magic bytes mismatch; must be `STR`
                raise AvaReadException(f"{self.path.name} is not a valid Avantes `STR` file.")
            fo.readinto(self._header)
            fo.seek(10000)  # Header plus a reserved (or padding) block always seems to be 10000 bytes.
            pixels, *_ = struct.unpack(
                "<hbhb", fo.read(6)
            )  # appears this block contains: (pixels, somevalue1, pixels, somevalue2)
            # next is some block of mysterious values of type double,but of value `1`. Some flag?
            # values = np.fromfile(fo, dtype=np.double, count = pixels)
            fo.seek(int(pixels * sizeof(c_double)), os.SEEK_CUR)  # skip for now
            self._wavelength = np.fromfile(fo, dtype=np.double, count=pixels)
            self._dark = np.fromfile(fo, dtype=np.double, count=pixels)
            self._ref = np.fromfile(fo, dtype=np.double, count=pixels)
            self.delay = np.zeros(self.preamble.frames)
            self.data = np.zeros((pixels, self.preamble.frames), dtype=np.double)
            stride = pixels * sizeof(c_double)  # noqa: F841
            for i in range(self.preamble.frames):
                self.delay[i] = struct.unpack("l", fo.read(sizeof(c_long)))[0] / 100  # `unpack` return tuple
                self.data[:, i] = np.fromfile(fo, dtype=np.double, count=pixels)

    def __repr__(self):
        """Representation of the STRFile as a  string."""
        return f"STRFile({self.ID.SerialNumber}, frames={self.preamble.frames})"

    def __getattr__(self, name: str):
        """Allow access to metadata from the header struct, mapped to python native types.

        This performs a lookup for attributes that are not already defined (i.e. those that are not actual defined class or instance attributes).

        If the given `name` is a valid field of the [`_header`][..], it will be returned as if it were an attribute.

        The [`_mapping`][..] attribute is a `Mapping` proxy of header for mapping C types to python native types.
        """
        return getattr(self._mapping, name)

    def __getitem__(self, index: int):
        """Implement getting a frame by index, emulating behaviour of a list.

        Along with `__len__` this makes the class iterable, i.e. one can iterate over channels contained within.
        """
        return self.data[self.Measurement.StartPixel : self.Measurement.StopPixel, index] - self.dark

    def __len__(self):
        """Return amount of frames contained in file."""
        return self.preamble.frames

    @property
    def serial(self):
        """The serial of the spectrometer."""
        return self.ID.SerialNumber

    @property
    def name(self):
        """The name of the file, including extension."""
        return self.path.name

    @property
    def frames(self) -> int:
        """Return the amount of frames stored in the file."""
        return self.preamble.frames

    @property
    def pixels(self):
        """Return the amount of active pixels of the acquisition.

        Note:
            This can be different from the total pixel count of the sensor if some pixels are deactivated.
        """
        return self.Measurement.StopPixel - self.Measurement.StartPixel

    @property
    def exposure(self):
        """The exposure time used in milliseconds.

        Sometimes also called `integration time` of the sensor.
        """
        return self.Measurement.IntegrationTime

    @property
    def wavelength(self):
        """Return the wavelength array, constrained to the range of active pixels."""
        return self._wavelength[self.Measurement.StartPixel : self.Measurement.StopPixel]

    @property
    def scope(self):
        """The raw signal from the spectrometer, as stored in the file.

        Called the 'Scope' data (or RawScope) by Avantes.
        """
        return self.data[self.Measurement.StartPixel : self.Measurement.StopPixel, :]

    @property
    def dark(self):
        """Return the Dark signal array (or background), constrained to the range of active pixels."""
        return self._dark[self.Measurement.StartPixel : self.Measurement.StopPixel]

    @property
    def ref(self):
        """Return the Reference signal array, constrained to the range of active pixels."""
        return self._ref[self.Measurement.StartPixel : self.Measurement.StopPixel]

    @property
    def signal(self):
        """Return the dark-corrected signal for all frames, constrained to the range of active pixels."""
        return self.data[self.Measurement.StartPixel : self.Measurement.StopPixel, :] - self.dark


def read_file(file_path: Path) -> AVSFile | STRFile:
    """Open a file saved by Avantes AvaSoft.

    Detects the file type from the file and returns a corresponding instance of [`AVSFile`][(m).AVSFile] or [`STRFile`][(m).STRFile].
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"{file_path} does not exist")
    elif file_path.is_dir():
        raise FileNotFoundError(f"{file_path} is a directory, please provide a file path")
    with file_path.open("rb") as fo:
        prelude = fo.read(5)
    file_format = prelude[:3].decode()
    file_version = int(prelude[3:5]) / 10
    if file_format.upper() == "AVS":
        if file_version < 8:
            raise AvaReadException(f"File version {file_version} is not supported.")
        return AVSFile(file_path)
    elif file_format.upper() == "STR":
        if file_version < 8:
            raise AvaReadException(f"File version {file_version} is not supported.")
        return STRFile(file_path)
    else:
        raise AvaReadException(f"{file_path.name} is not a valid Avantes AvaSoft 8 file.")
