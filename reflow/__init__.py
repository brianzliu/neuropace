"""Legacy import adapter. New code should import :mod:`neuropace`."""

from neuropace import __path__ as _neuropace_path
from neuropace import __version__

# Let old imports such as ``reflow.config`` resolve to the renamed package.
__path__ = _neuropace_path

__all__ = ["__version__"]
