"""Label feedback strategies for different controller capabilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from padbound import Controller


class LabelFeedbackStrategy(ABC):
    """Base class for label pad feedback strategies."""

    @abstractmethod
    def update_feedback(self, selected_label: int, label_colors: list[str]) -> None:
        """Update pad feedback based on selected label.

        Args:
            selected_label: Index of the currently selected label (0 = eraser).
            label_colors: List of hex color strings for each label.
        """
        pass

    @abstractmethod
    def initialize(self, label_colors: list[str]) -> None:
        """Initialize pads with label colors.

        Args:
            label_colors: List of hex color strings for each label.
        """
        pass


class RGBColorStrategy(LabelFeedbackStrategy):
    """RGB pads: show label colors, selected label pulses if supported."""

    def __init__(
        self, controller: Controller, pad_ids: list[str], supports_pulse: bool
    ) -> None:
        """Initialize RGB color strategy.

        Args:
            controller: The padbound Controller instance.
            pad_ids: List of pad control IDs.
            supports_pulse: Whether the controller supports pulsing LEDs.
        """
        self.controller = controller
        self.pad_ids = pad_ids
        self.supports_pulse = supports_pulse

    def initialize(self, label_colors: list[str]) -> None:
        """Initialize pads with label colors."""
        self.update_feedback(0, label_colors)

    def update_feedback(self, selected_label: int, label_colors: list[str]) -> None:
        """Update pad colors and highlight selected label.

        Uses set_state() for each pad - works on ALL RGB controllers regardless
        of whether they support persistent configuration.

        Args:
            selected_label: Index of the currently selected label.
            label_colors: List of hex color strings for each label.
        """
        for i, pad_id in enumerate(self.pad_ids):
            color = label_colors[i] if i < len(label_colors) else "#808080"
            led_mode = (
                "pulse" if (i == selected_label and self.supports_pulse) else "solid"
            )
            self.controller.set_state(
                pad_id,
                is_on=True,
                color=color,
                led_mode=led_mode,
            )


class ToggleStrategy(LabelFeedbackStrategy):
    """No color: use mutually exclusive toggles (ON = selected)."""

    def __init__(
        self, controller: Controller, pad_ids: list[str], supports_pulse: bool
    ) -> None:
        """Initialize toggle strategy.

        Args:
            controller: The padbound Controller instance.
            pad_ids: List of pad control IDs.
            supports_pulse: Whether the controller supports pulsing LEDs.
        """
        self.controller = controller
        self.pad_ids = pad_ids
        self.supports_pulse = supports_pulse

    def initialize(self, label_colors: list[str]) -> None:
        """Initialize pads - first pad (eraser) ON by default."""
        self.update_feedback(0, label_colors)

    def update_feedback(self, selected_label: int, label_colors: list[str]) -> None:
        """Update toggle states - only selected label is ON.

        Args:
            selected_label: Index of the currently selected label.
            label_colors: Ignored for toggle strategy.
        """
        for i, pad_id in enumerate(self.pad_ids):
            is_selected = i == selected_label
            led_mode = "pulse" if (is_selected and self.supports_pulse) else "solid"
            self.controller.set_state(
                pad_id,
                is_on=is_selected,
                led_mode=led_mode,
            )


class NoFeedbackStrategy(LabelFeedbackStrategy):
    """No feedback capability: pads work but no visual indication."""

    def initialize(self, label_colors: list[str]) -> None:
        """No-op for controllers without feedback."""
        pass

    def update_feedback(self, selected_label: int, label_colors: list[str]) -> None:
        """No-op for controllers without feedback."""
        pass


def create_feedback_strategy(
    controller: Controller,
    pad_ids: list[str],
) -> LabelFeedbackStrategy:
    """Factory: choose strategy based on controller capabilities.

    Args:
        controller: The padbound Controller instance.
        pad_ids: List of pad control IDs.

    Returns:
        Appropriate LabelFeedbackStrategy for the controller.
    """
    if not pad_ids:
        return NoFeedbackStrategy()

    # Check first pad's capabilities
    controls = controller.get_controls()
    first_pad = next(
        (c for c in controls if c.control_id == pad_ids[0]),
        None,
    )
    if not first_pad:
        return NoFeedbackStrategy()

    caps = first_pad.capabilities
    supported_modes = caps.supported_led_modes or []
    supports_pulse = "pulse" in supported_modes

    if caps.supports_color and caps.color_mode == "rgb":
        return RGBColorStrategy(controller, pad_ids, supports_pulse)
    elif caps.supports_feedback:
        return ToggleStrategy(controller, pad_ids, supports_pulse)
    else:
        return NoFeedbackStrategy()
