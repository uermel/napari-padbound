"""Unified viewer controller for napari using any MIDI controller."""

from __future__ import annotations

from typing import TYPE_CHECKING

import napari

from napari_padbound.control_mapper import ControlMapper
from napari_padbound.label_feedback import create_feedback_strategy

if TYPE_CHECKING:
    from padbound import Controller
    from padbound.controls import ControlState


class ViewerController:
    """Controls napari viewer using any MIDI controller.

    Automatically discovers and maps available controls to features:
    - Slice navigation (coarse + fine)
    - Zoom control
    - Brush size
    - Label selection via pads

    Features gracefully degrade based on controller capabilities.
    """

    MIN_ZOOM = 0.1
    MAX_ZOOM = 10.0
    MIN_BRUSH_SIZE = 1
    MAX_BRUSH_SIZE = 100

    def __init__(self, viewer: napari.Viewer, midi_controller: Controller) -> None:
        """Initialize the viewer controller.

        Args:
            viewer: The napari viewer instance.
            midi_controller: The padbound Controller instance.
        """
        self.viewer = viewer
        self.midi_controller = midi_controller
        self._labels_layer: napari.layers.Labels | None = None

        # Slice navigation state
        self.max_slices = 0
        self.slice_axis = 0
        self.coarse_value = 0
        self.fine_value = 64  # Center at 64 (no offset)

        # Discover controls and create mapping
        mapper = ControlMapper(midi_controller)
        self.mapping = mapper.create_mapping()
        self.mapping_info = mapper.get_mapping_info()

        # Create feedback strategy for label pads
        self.label_feedback = create_feedback_strategy(
            midi_controller,
            self.mapping.label_pads,
        )

        self._setup_callbacks()
        self._setup_napari_events()

        # Initialize from current state
        self._update_slice_range()
        self._check_active_layer()

    def _setup_callbacks(self) -> None:
        """Register callbacks for mapped controls."""
        if self.mapping.coarse_slice:
            self.midi_controller.on_control(
                self.mapping.coarse_slice, self._on_coarse_change
            )
        if self.mapping.fine_slice:
            self.midi_controller.on_control(
                self.mapping.fine_slice, self._on_fine_change
            )
        if self.mapping.zoom:
            self.midi_controller.on_control(self.mapping.zoom, self._on_zoom_change)
        if self.mapping.brush_size:
            self.midi_controller.on_control(
                self.mapping.brush_size, self._on_brush_change
            )

        # Register pad callbacks for label selection
        for i, pad_id in enumerate(self.mapping.label_pads):
            self.midi_controller.on_control(
                pad_id,
                lambda state, idx=i: self._on_label_select(state, idx),
            )

    def _setup_napari_events(self) -> None:
        """Connect to napari layer events."""
        self.viewer.layers.events.inserted.connect(self._on_layer_inserted)
        self.viewer.layers.selection.events.changed.connect(self._on_selection_changed)

    # --- Slice navigation ---

    def _on_coarse_change(self, state: ControlState) -> None:
        """Handle coarse slice control change."""
        self.coarse_value = state.value
        self._update_viewer_slice()

    def _on_fine_change(self, state: ControlState) -> None:
        """Handle fine slice control change."""
        self.fine_value = state.value
        self._update_viewer_slice()

    def _compute_slice(self) -> int:
        """Calculate target slice from coarse + fine values."""
        if self.max_slices > 0:
            base_slice = int((self.coarse_value / 127) * self.max_slices)
        else:
            base_slice = 0

        # Fine: center at 64, so 0=-64 offset, 127=+63 offset
        offset = self.fine_value - 64

        return max(0, min(self.max_slices, base_slice + offset))

    def _update_viewer_slice(self) -> None:
        """Apply computed slice to napari viewer."""
        if self.max_slices <= 0:
            return
        target_slice = self._compute_slice()
        self.viewer.dims.set_current_step(self.slice_axis, target_slice)

    def _update_slice_range(self) -> None:
        """Update max_slices based on active layer."""
        active = self.viewer.layers.selection.active
        if active is None:
            return

        if not isinstance(active, (napari.layers.Image, napari.layers.Labels)):
            return

        if active.data.ndim < 3:
            return

        self.slice_axis = 0
        self.max_slices = active.data.shape[self.slice_axis] - 1

    # --- Zoom ---

    def _on_zoom_change(self, state: ControlState) -> None:
        """Handle zoom control - logarithmic mapping."""
        normalized = state.normalized_value
        zoom = self.MIN_ZOOM * ((self.MAX_ZOOM / self.MIN_ZOOM) ** normalized)
        self.viewer.camera.zoom = zoom

    # --- Brush size ---

    def _on_brush_change(self, state: ControlState) -> None:
        """Handle brush size control - logarithmic mapping."""
        if self._labels_layer is None:
            return

        normalized = state.normalized_value
        brush_size = self.MIN_BRUSH_SIZE * (
            (self.MAX_BRUSH_SIZE / self.MIN_BRUSH_SIZE) ** normalized
        )
        self._labels_layer.brush_size = int(brush_size)

    # --- Label selection ---

    def _on_label_select(self, state: ControlState, label_index: int) -> None:
        """Handle pad press - select the corresponding label."""
        print("_on_label_select", label_index)
        if not state.is_on:  # Only act on press, not release
            return
        if self._labels_layer is None:
            return

        self._labels_layer.selected_label = label_index
        self._update_label_feedback()

    def _update_label_feedback(self) -> None:
        """Update pad feedback to reflect selected label."""
        print("_update_label_feedback")
        if self._labels_layer is None:
            return

        label_colors = self._get_label_colors()
        selected = self._labels_layer.selected_label
        self.label_feedback.update_feedback(selected, label_colors)

    def _get_label_colors(self) -> list[str]:
        """Get hex colors for labels 0-7 from the active layer."""
        colors = []
        for i in range(len(self.mapping.label_pads)):
            if i == 0:
                colors.append("#FFFFFF")  # Eraser is white
            else:
                rgba = self._get_label_color(i)
                colors.append(self._rgba_to_hex(rgba))
        return colors

    def _get_label_color(self, label_index: int) -> tuple:
        """Get RGBA color for a label from the layer's colormap."""
        layer = self._labels_layer
        if layer is None:
            return (0.5, 0.5, 0.5, 1.0)

        # Try direct color dict first
        if hasattr(layer, "color") and layer.color and label_index in layer.color:
            return layer.color[label_index]

        # Fall back to colormap
        if hasattr(layer, "colormap") and layer.colormap is not None:
            return layer.colormap.map(label_index)

        return (0.5, 0.5, 0.5, 1.0)

    def _rgba_to_hex(self, rgba: tuple) -> str:
        """Convert RGBA (0-1 floats) to hex string."""
        r = int(rgba[0] * 255)
        g = int(rgba[1] * 255)
        b = int(rgba[2] * 255)
        return f"#{r:02x}{g:02x}{b:02x}"

    # --- Layer events ---

    def _on_layer_inserted(self, event) -> None:
        """Handle new layer insertion."""
        print("_on_layer_inserted")
        layer = event.value
        if isinstance(layer, napari.layers.Labels):
            self._set_active_labels_layer(layer)
        self._update_slice_range()

    def _on_selection_changed(self, event) -> None:
        """Handle active layer selection change."""
        print("_on_selection_changed")
        self._check_active_layer()
        self._update_slice_range()

    def _check_active_layer(self) -> None:
        """Check if active layer is a Labels layer."""
        active = self.viewer.layers.selection.active
        if isinstance(active, napari.layers.Labels):
            self._set_active_labels_layer(active)

    def _set_active_labels_layer(self, layer: napari.layers.Labels) -> None:
        """Set the active labels layer and update feedback."""
        print("_set_active_labels_layer")
        self._labels_layer = layer
        label_colors = self._get_label_colors()
        # Use actual selected label from layer, not hardcoded 0
        selected = layer.selected_label
        self.label_feedback.update_feedback(selected, label_colors)
