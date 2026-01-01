"""Label feedback strategies for different controller capabilities."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from padbound.config import ControlConfig, ControllerConfig
from padbound.controls import ControlType, LEDAnimationType, LEDMode, StateUpdate

if TYPE_CHECKING:
    from padbound import Controller

logger = logging.getLogger(__name__)


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

    def __init__(self, controller: Controller, pad_ids: list[str], supports_pulse: bool) -> None:
        """Initialize RGB color strategy.

        Args:
            controller: The padbound Controller instance.
            pad_ids: List of pad control IDs.
            supports_pulse: Whether the controller supports pulsing LEDs.
        """
        self.controller = controller
        self.pad_ids = pad_ids
        self.supports_pulse = supports_pulse
        # Debouncing: track last state to skip redundant updates
        self._last_selected: int | None = None
        self._last_colors: list[str] | None = None

    def initialize(self, label_colors: list[str]) -> None:
        """Initialize pads with label colors."""
        self.update_feedback(0, label_colors)

    def update_feedback(self, selected_label: int, label_colors: list[str]) -> None:
        """Update pad colors and highlight selected label.

        Updates control definitions with new colors/LED modes, then sends
        visual feedback to the hardware. This ensures toggle behavior uses
        correct colors when pads are pressed.

        Uses set_states() batch API for efficient multi-pad updates. This allows
        hardware-specific optimizations (e.g., single SysEx for LPD8, proper timing
        for APC mini) while keeping this code controller-agnostic.

        Args:
            selected_label: Index of the currently selected label.
            label_colors: List of hex color strings for each label.
        """
        # Debouncing: skip if nothing changed (prevents duplicate updates)
        if selected_label == self._last_selected and label_colors == self._last_colors:
            return

        # Update tracking state
        self._last_selected = selected_label
        self._last_colors = list(label_colors)  # Copy to avoid mutation issues

        # Step 1: Build config with new colors for each pad
        # This ensures toggle behavior uses correct colors when pads are pressed
        controls_config = {}
        for i, pad_id in enumerate(self.pad_ids):
            color = label_colors[i] if i < len(label_colors) else "#808080"

            if self.supports_pulse:
                # OFF = solid color, ON = pulsing color
                controls_config[pad_id] = ControlConfig(
                    type=ControlType.TOGGLE,
                    on_color=color,
                    off_color=color,
                    on_led_mode="pulse",
                    off_led_mode="solid",
                )
            else:
                # OFF = dimmed, ON = bright (use same color, hardware handles dimming)
                controls_config[pad_id] = ControlConfig(
                    type=ControlType.TOGGLE,
                    on_color=color,
                    off_color=color,
                    on_led_mode="solid",
                    off_led_mode="solid",
                )

        # Step 2: Reconfigure to update definitions (in-memory only for performance)
        config = ControllerConfig(controls=controls_config)
        print(config)
        self.controller.reconfigure(config, update_in_memory_only=False)

        # Step 3: Update current visual state
        updates = []
        for i, pad_id in enumerate(self.pad_ids):
            color = label_colors[i] if i < len(label_colors) else "#808080"
            is_selected = i == selected_label
            led_mode = (
                LEDMode(animation_type=LEDAnimationType.PULSE)
                if (is_selected and self.supports_pulse)
                else LEDMode(animation_type=LEDAnimationType.SOLID)
            )
            updates.append((pad_id, StateUpdate(is_on=is_selected, color=color, led_mode=led_mode)))
        print(updates)
        print(f"selected {selected_label}")
        print(f"supports pulse: {self.supports_pulse}")
        self.controller.set_states(updates)


class ToggleStrategy(LabelFeedbackStrategy):
    """No color: use mutually exclusive toggles (ON = selected)."""

    def __init__(self, controller: Controller, pad_ids: list[str], supports_pulse: bool) -> None:
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

        Updates control definitions with on/off colors, then sends
        visual feedback to the hardware. For controllers without color support,
        uses black for OFF and white for ON.

        Uses set_states() batch API for efficient multi-pad updates.

        Args:
            selected_label: Index of the currently selected label.
            label_colors: Ignored for toggle strategy (no color support).
        """
        # Step 1: Build config with on/off colors for each pad
        # OFF = black, ON = white (no color support)
        controls_config = {}
        for pad_id in self.pad_ids:
            controls_config[pad_id] = ControlConfig(
                type=ControlType.TOGGLE,
                on_color="#FFFFFF",
                off_color="#000000",
                on_led_mode="pulse" if self.supports_pulse else "solid",
                off_led_mode="solid",
            )

        # Step 2: Reconfigure to update definitions (in-memory only for performance)
        config = ControllerConfig(controls=controls_config)
        self.controller.reconfigure(config, update_in_memory_only=True)

        # Step 3: Update current visual state
        updates = []
        for i, pad_id in enumerate(self.pad_ids):
            is_selected = i == selected_label
            led_mode = (
                LEDMode(animation_type=LEDAnimationType.PULSE)
                if (is_selected and self.supports_pulse)
                else LEDMode(animation_type=LEDAnimationType.SOLID)
            )
            updates.append((pad_id, StateUpdate(is_on=is_selected, led_mode=led_mode)))
        self.controller.set_states(updates)


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
    supports_pulse = LEDAnimationType.PULSE in [mode.animation_type for mode in supported_modes]

    if caps.supports_color and caps.color_mode == "rgb":
        return RGBColorStrategy(controller, pad_ids, supports_pulse)
    elif caps.supports_feedback:
        return ToggleStrategy(controller, pad_ids, supports_pulse)
    else:
        return NoFeedbackStrategy()
