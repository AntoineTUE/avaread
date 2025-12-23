# AvaRead

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18018067.svg)](https://doi.org/10.5281/zenodo.18018067)
[![GitHub License](https://img.shields.io/github/license/AntoineTUE/avaread)](https//www.github.com/AntoineTUE/avaread/blob/main/LICENSE)
[![GitHub Workflow Status build](https://img.shields.io/github/actions/workflow/status/AntoineTUE/avaread/build.yml?label=PyPI%20build)](https://pypi.python.org/pypi/avaread)
[![GitHub Workflow Status docs](https://img.shields.io/github/actions/workflow/status/AntoineTUE/avaread/docs-dev.yml?label=Documentation%20build)](https://antoinetue.github.io/avaread)
[![PyPI - Version](https://img.shields.io/pypi/v/avaread)](https://pypi.python.org/pypi/avaread)
[![PyPI - Python versions](https://img.shields.io/pypi/pyversions/avaread.svg)](https://pypi.python.org/pypi/avaread)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/avaread)](https://pypistats.org/packages/avaread)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)

A project for reading spectra from [Avantes AvaSoft 8](https://www.avantes.com/products/software/avasoft/) files in Python.

It supports all Avantes multichannel files (e.g. `.raw8`, `.rir8`, etc.), reading all avaible channels, as well as store-to-RAM/multiframe files (`.str8`).

Importantly, this means you can work with these files directly in your analysis!

* No need to convert your `.raw8` (or equivalent files) to work with them

* No need to convert your `.str8` into large sets of files with very similar names!

## Installing

`AvaRead` can be easily installed with `pip` and only has `numpy` as a dependency, which will be installed if missing.

You can install the latest release from PyPI:

```shell
pip install avaread
```

To install the latest development version from GitHub, you can use:

```shell
pip install git+https://github.com/AntoineTUE/avaread.git
```

## How to use

Using `avaread` is fairly straightforward, you should be fine with using the `read_file` function to open any Avantes AvaSoft 8 file.

Depending on the detected file type, you will either receive an instance of `AVSFile` or `STRFile`, which are iterable, container-like objects that give you access to the data and metadata read from the file.

Most of the data is stored as `numpy.ndarray`s under the hood.

Note that these files store data differently:

* `AVSFile` stores data from multiple devices (or channels), one spectrum per device, which can be of different shape.
* `STRFile` stores multiple spectra recorded in sequence by a single device (or channel).

See also the [documentation](https://antoinetue.github.io/avaread) for more details and examples.

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
# Plot the different channels stored in the `AVSFile`
for channel in data1:
    plt.plot(channel.wavelength, channel.signal, label=f"{channel.ID.SerialNumber}")

plt.figure()
# Plot the different frames stored in the `STRFile`
for i, frame in enumerate(data2):
    plt.plot(data2.wavelength, frame, label=f"Delay: {data2.delay[i]} ms")
```

## License

AvaRead is licensed under the MIT license.

See [LICENSE](./LICENSE).
