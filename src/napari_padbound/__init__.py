try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from .control_mapper import ControlMapper, ControlMapping
from .label_feedback import (
    LabelFeedbackStrategy,
    NoFeedbackStrategy,
    RGBColorStrategy,
    ToggleStrategy,
    create_feedback_strategy,
)
from .viewer_controller import ViewerController
from .widget import PadboundWidget

__all__ = (
    "ControlMapper",
    "ControlMapping",
    "LabelFeedbackStrategy",
    "NoFeedbackStrategy",
    "RGBColorStrategy",
    "ToggleStrategy",
    "create_feedback_strategy",
    "ViewerController",
    "PadboundWidget",
)
