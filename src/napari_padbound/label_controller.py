"""Label Palette Controller for napari using padbound library."""

from __future__ import annotations

from typing import TYPE_CHECKING

import napari
from padbound import BankConfig, ControlConfig, ControllerConfig, ControlType

if TYPE_CHECKING:
    from padbound import Controller
    from padbound.controls import ControlState


class LabelPaletteController:
    """Controls napari label selection and brush size via MIDI pads/knobs.

    Uses 8 RGB pads as a color palette:
    - Pad 1 = Eraser (label 0, white LED)
    - Pads 2-8 = Labels 1-7 with matching colors from colormap

    Uses one knob for brush size control with logarithmic scaling.
    """

    BRUSH_KNOB = "knob_2@bank_1"
    PAD_IDS = [f"pad_{i}@bank_1" for i in range(1, 9)]  # pad_1 to pad_8

    MIN_BRUSH_SIZE = 1
    MAX_BRUSH_SIZE = 100

    def __init__(self, viewer: napari.Viewer, midi_controller: Controller) -> None:
        """Initialize the label palette controller.

        Args:
            viewer: The napari viewer instance.
            midi_controller: Shared padbound Controller instance.
        """
        self.viewer = viewer
        self.midi_controller = midi_controller
        self._active_labels_layer: napari.layers.Labels | None = None

        self._setup_pad_callbacks()
        self._setup_knob_callback()
        self._setup_napari_events()

        # Initialize from current active layer if available
        self._check_active_layer()

    def _setup_pad_callbacks(self) -> None:
        """Register callbacks for each pad."""
        for i, pad_id in enumerate(self.PAD_IDS):
            label_index = i  # pad_1 → label 0 (eraser), pad_2 → label 1, etc.
            self.midi_controller.on_control(
                pad_id,
                lambda state, idx=label_index: self._on_pad_press(state, idx),
            )

    def _setup_knob_callback(self) -> None:
        """Register callback for brush size knob."""
        self.midi_controller.on_control(self.BRUSH_KNOB, self._on_brush_knob)

    def _setup_napari_events(self) -> None:
        """Connect to napari layer events."""
        self.viewer.layers.events.inserted.connect(self._on_layer_inserted)
        self.viewer.layers.selection.events.changed.connect(self._on_selection_changed)

    def _on_pad_press(self, state: ControlState, label_index: int) -> None:
        """Handle pad press - select the corresponding label.

        Args:
            state: The control state from padbound.
            label_index: The label index to select (0 = eraser).
        """
        if not state.is_on:  # Only act on press, not release
            return
        if self._active_labels_layer is None:
            return
        self._active_labels_layer.selected_label = label_index

    def _on_brush_knob(self, state: ControlState) -> None:
        """Handle brush size knob - logarithmic mapping.

        Args:
            state: The control state from padbound.
        """
        if self._active_labels_layer is None:
            return

        # Logarithmic mapping: normalized (0-1) → brush size (1-100)
        # Formula: size = min * (max/min)^normalized
        normalized = state.normalized_value
        brush_size = self.MIN_BRUSH_SIZE * (
            (self.MAX_BRUSH_SIZE / self.MIN_BRUSH_SIZE) ** normalized
        )
        self._active_labels_layer.brush_size = int(brush_size)

    def _on_layer_inserted(self, event) -> None:
        """Handle new layer insertion.

        Args:
            event: The layer insertion event.
        """
        layer = event.value
        if isinstance(layer, napari.layers.Labels):
            self._set_active_labels_layer(layer)

    def _on_selection_changed(self, event) -> None:
        """Handle active layer selection change.

        Args:
            event: The selection change event.
        """
        self._check_active_layer()

    def _check_active_layer(self) -> None:
        """Check if active layer is a Labels layer and update accordingly."""
        active = self.viewer.layers.selection.active
        if isinstance(active, napari.layers.Labels):
            self._set_active_labels_layer(active)

    def _set_active_labels_layer(self, layer: napari.layers.Labels) -> None:
        """Set the active labels layer and update pad colors.

        Args:
            layer: The Labels layer to use.
        """
        self._active_labels_layer = layer
        self._update_pad_colors()

    def _update_pad_colors(self) -> None:
        """Update pad LED colors using reconfigure().

        Builds a new ControllerConfig with colors from the Labels layer
        colormap and applies it via reconfigure().
        """
        if self._active_labels_layer is None:
            return

        # Build new config with colors from Labels layer
        pad_configs = {}
        for i in range(1, 9):  # pad_1 to pad_8
            label_index = i - 1  # pad_1 → label 0, etc.

            if label_index == 0:
                color_hex = "#FFFFFF"  # Eraser is always white
            else:
                rgba = self._get_label_color(label_index)
                color_hex = self._rgba_to_hex(rgba)

            pad_configs[f"pad_{i}"] = ControlConfig(
                type=ControlType.MOMENTARY,
                color=color_hex,
            )

        # Reconfigure the controller with new colors
        new_config = ControllerConfig(
            banks={
                "bank_1": BankConfig(
                    toggle_mode=False,
                    controls=pad_configs,
                ),
            },
        )
        self.midi_controller.reconfigure(new_config)

    def _get_label_color(self, label_index: int) -> tuple:
        """Get RGBA color for a label from the layer's colormap.

        Args:
            label_index: The label index to get color for.

        Returns:
            RGBA tuple with values in 0-1 range.
        """
        layer = self._active_labels_layer
        if layer is None:
            return (0.5, 0.5, 0.5, 1.0)  # Gray fallback

        # Try direct color dict first
        if hasattr(layer, "color") and layer.color and label_index in layer.color:
            return layer.color[label_index]

        # Fall back to colormap
        if hasattr(layer, "colormap") and layer.colormap is not None:
            return layer.colormap.map(label_index)

        return (0.5, 0.5, 0.5, 1.0)  # Gray fallback

    def _rgba_to_hex(self, rgba: tuple) -> str:
        """Convert RGBA (0-1 floats) to hex string.

        Args:
            rgba: RGBA tuple with values in 0-1 range.

        Returns:
            Hex color string like '#FF0000'.
        """
        r = int(rgba[0] * 255)
        g = int(rgba[1] * 255)
        b = int(rgba[2] * 255)
        return f"#{r:02x}{g:02x}{b:02x}"
