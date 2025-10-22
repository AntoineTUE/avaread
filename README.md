# AvaRead

A project for reading spectra from Avantes AvaSoft files inPython.

It supports all Avantes multichannel files (e.g. `raw8`, `rir8`, etc.), reading all avaible channels.

Support for Store-to-RAM files (`str8`) is in the works.

[TOC]

## Installing
`AvaRead` can be installed with `pip`.

To install the latest version, download/clone it from the project page and run the following command in the downloaded folder.
This will install an `editable` release that will reflect any changes you make.

```console
pip install -e .
```

Further optional features can be installed by specifying the feature flag, as defined in the [pyproject.toml](./pyproject.toml).

To install all dependencies to locally serve and update the documentation for instance, you can run:

```console
pip install -e .[docs]
```

## How to use

Using `avaread` is fairly straightforward, you should be fine with using the `read_file` function to open any Avantes AvaSoft file.

Depending on the detected file type, you will eithe receive an instance of `AVSFile` or `STRFile`, which are interable, container-like objects that give you access to the data and metadata read from the file.

```python
import avaread
from avaread.reader import AVSFile, STRFile
from pathlib import Path
import matplotlib.pyplot as plt

file1 = Path("path/to/file1.raw8")
file2 = Path("path/to/file2.str8")

data1 = avaread.read_file(file1)
data2 = avaread.read_file(file2)

assert isinstance(data1, AVSFile)
assert isinstance(data2, STRFile)

plt.figure()
for channel in data1:
    plt.plot(channel.wavelength, channel.signal, label=f"{channel.ID.SerialNumber}")

plt.figure()
for i, frame in enumerate(data2):
    plt.plot(data2.wavelength, frame, label=f"Delay: {data2.delay[i]} ms")
```

## License

AvaRead is licensed under the MIT license.

See [LICENSE](LICENSE).
