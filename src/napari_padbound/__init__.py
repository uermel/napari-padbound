try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from .label_controller import LabelPaletteController
from .slice_controller import MidiSliceController
from .widget import PadboundWidget

__all__ = ("LabelPaletteController", "MidiSliceController", "PadboundWidget")
