"""goldtable: snapshot testing for data pipeline outputs."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("goldtable")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without install
    __version__ = "0.0.0"

__all__ = ["__version__"]
