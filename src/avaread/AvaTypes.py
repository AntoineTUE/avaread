"""Type definitions of mainly C Structures and Enums.

These structures and enums respresent the way how an Avantes spectrometer interfaces with a PC, based on the SDK documentation and the `avaspec.h` header file.

Only the types (and constants) are defined that are needed for parsing the `AVS` type files, not the complete definition from the SDK.

In addition, a few extra Structures have been defined that aim to represent the structure of the file header for different types of file formats:

* [AVSPreamble][(m).AVSPreamble]: The preamble of a regular AVS file, specifying the file type and channel count.

* [AVSInfoBlock][(m).AVSInfoBlock]: The header block with metadata for a spectrometer channel stored in an AVS file.

* [STRPreamble][(m).STRPreamble]: The preamble of a Store-to-RAM file, specifying the file type and frame count.

* [STRInfoBlock][(m).STRInfoBlock]: The header block with metadata for Store-to-RAM files.
"""

import ctypes
from ctypes import Structure, Array, c_char, c_ubyte, c_uint16, c_uint32, c_byte, c_float, c_double
from enum import IntEnum
import numpy as np
from typing import Any, TypeVar, Union, ClassVar

# CType = TypeVar("CType", bound=ctypes._SimpleCData)  # Allows ctypes types

AVS_SERIAL_LEN = 10
USER_ID_LEN = 64


class DeviceStatus(IntEnum):
    """Enumeration of the different status codes for a device."""

    UNKNOWN = 0
    USB_AVAILABLE = 1
    USB_IN_USE_BY_APPLICATION = 2
    USB_IN_USE_BY_OTHER = 3
    ETH_AVAILABLE = 4
    ETH_IN_USE_BY_APPLICATION = 5
    ETH_IN_USE_BY_OTHER = 6
    ETH_ALREADY_IN_USE_USB = 7


class MeasurementEnum(IntEnum):
    """Enumeration of the different measurement modes of AvaSoft."""

    Scope = 0
    ScopeDarkCorrected = 1
    Absorbance = 2
    Transmission = 3
    Reflectance = 4
    Irradiance = 5
    RelativeIrradiance = 6
    Temperature = 7


class TrigMode(IntEnum):
    """Enumerate supported trigger modes."""

    SW = 0
    HW = 1


class TrigSource(IntEnum):
    """Enumerate supported trigger sources."""

    SINGLE = 2
    EXT = 0
    SYNC = 1


class TrigKind(IntEnum):
    """Enumerate supported trigger types."""

    EDGE = 0
    LEVEL = 1


class MappableStructure(Structure):
    """A C structure with support for mapping fields to enums."""

    _pack_: ClassVar[int] = 1
    _fields_: ClassVar[list[tuple[str, Any]]] = []
    _map: ClassVar[dict] = {}


class AvsIdentityStruct(MappableStructure):
    """IdentityType Structure."""

    _pack_ = 1
    _fields_ = [
        ("SerialNumber", c_char * AVS_SERIAL_LEN),
        ("UserFriendlyName", c_char * USER_ID_LEN),
        ("Status", c_ubyte),
    ]

    _map = {"Status": DeviceStatus}


class DarkCorrectionStruct(MappableStructure):
    """DarkCorrectionType Structure."""

    _pack_ = 1
    _fields_ = [
        ("Enable", c_ubyte),
        ("ForgetPercentage", c_ubyte),
    ]


class SmoothingStruct(MappableStructure):
    """SmoothingType Structure."""

    _pack_ = 1
    _fields_ = [
        ("SmoothPix", c_uint16),
        ("SmoothModel", c_ubyte),
    ]


class TriggerStruct(MappableStructure):
    """TriggerType Structure."""

    _pack_ = 1
    _fields_ = [
        ("Mode", c_ubyte),
        ("Source", c_ubyte),
        ("SourceType", c_ubyte),
    ]

    _map = {"Mode": TrigMode, "Source": TrigSource, "SourceType": TrigKind}


class ControlSettingsStruct(MappableStructure):
    """ControlSettingsType Structure."""

    _pack_ = 1
    _fields_ = [
        ("StrobeControl", c_uint16),
        ("LaserDelay", c_uint32),
        ("LaserWidth", c_uint32),
        ("LaserWaveLength", c_float),
        ("StoreToRam", c_uint16),
    ]


class MeasConfigStruct(MappableStructure):
    """MeasConfigType Structure."""

    _pack_ = 1
    _fields_ = [
        ("StartPixel", c_uint16),
        ("StopPixel", c_uint16),
        ("IntegrationTime", c_float),
        ("IntegrationDelay", c_uint32),
        ("NrAverages", c_uint32),
        ("CorDynDark", DarkCorrectionStruct),
        ("Smoothing", SmoothingStruct),
        ("SaturationDetection", c_ubyte),
        ("Trigger", TriggerStruct),
        ("Control", ControlSettingsStruct),
    ]


class MiscInfoStruct(MappableStructure):
    """A structure containing miscellaneous information stored in a file.

    This block of fields can be found both in AVS and STR files, but is not defined or documented for the AvaSDK.
    """

    _fields_ = [
        ("file_datetime", c_uint32),  # not a TimeStampType
        ("detectorTemp", c_float),
        ("boardTemp", c_float),
        ("skip_float", c_float),  # likely NTC2 temperature or voltage (optional analog termistor)
        ("ColorTemperature", c_float),
        ("CalIntTime", c_float),
    ]


class AVSPreamble(MappableStructure):
    """The very start if an Avantes `AVS` file that contain data from one or more spectrometers.

    This header contains information on the file type, file version and amount of channels.

    Note that all files that start with the `AVS` magic bytes are supported, this corresponds to all 'regular' files being supported.

    STR (Store-to-RAM) files have a different preamble.
    """

    _fields_ = [
        ("FileType", c_char * 3),  # b"AVS"
        ("Version", c_char * 2),
        ("channels", c_ubyte),
    ]


class AVSInfoBlock(MappableStructure):
    """A metadata header for each block in a AVS file.

    This header corresponds to a single spectrometer, or spectrometer channel (for a multi channel device).
    """

    _fields_ = [
        ("blockLength", c_uint16),  # 32-bit does not work, it gives wrong block size.
        ("Unused1", c_byte * 2),  # Not clear
        ("channelIndex", c_byte),
        ("measurementEnum", c_ubyte),
        ("Unused2", c_byte * 2),  # Could contain data, could be a guard block
        ("ID", AvsIdentityStruct),
        ("Measurement", MeasConfigStruct),
        (
            "timestamp",
            c_uint32,
        ),  # either internal clock time of microcontroller in 10 us steps, or time of frame in kinetic series if DSTR export
        ("Misc", MiscInfoStruct),
        ("aFit", c_double * 5),
        ("comment", c_char * 130),
    ]

    _map = {"measurementEnum": MeasurementEnum}


class STRPreamble(MappableStructure):
    """The very start if an Avantes `STR` file that contains multiple spectra from a Store-to-RAM (STR) procedure.

    This header contains information on the file type, file version and amount of frames.

    Note that all files that start with the `STR` magic bytes are supported.

    Regular AVS files have a slightly different preamble.
    """

    _fields_ = [
        ("FileType", c_char * 3),  # b"STR"
        ("Version", c_char * 2),
        ("frames", c_uint16),  # Avasoft limits to setting to 65k
    ]


class STRInfoBlock(MappableStructure):
    """The metadata block at the start of a STR (Store-to-RAM) file, before the binary blob.

    This header corresponds to a single spectrometer, or spectrometer channel, but describes a sequence of spectra/frames stored in a STR procedure.

    """

    _fields_ = [
        ("Unused", c_byte * 5),  # Could contain data, could be a guard block
        ("ID", AvsIdentityStruct),
        ("Measurement", MeasConfigStruct),
        ("Unused1", c_byte * 7),
        ("Misc", MiscInfoStruct),
        (
            "Unused2",
            c_byte * 47,
        ),  # Needs to be explored further, starts at row \x080 in 16-wide Hex editor, offset= 128
        ("comment", c_char * 130),
    ]
