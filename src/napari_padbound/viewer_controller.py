"""Unified viewer controller for napari using any MIDI controller."""

from __future__ import annotations

from typing import TYPE_CHECKING

import napari
from padbound.config import BankConfig, ControllerConfig
from padbound.logging_config import get_logger

from napari_padbound.control_mapper import ControlMapper
from napari_padbound.label_feedback import NoFeedbackStrategy, create_feedback_strategy

logger = get_logger(__name__)

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

    MIN_ZOOM = 0.01
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

        # Configure MOMENTARY mode for controllers without LED feedback
        # This ensures pads work as discrete actions (press = select) rather than
        # toggles (which would require manual deselection since we can't turn them off)
        if isinstance(self.label_feedback, NoFeedbackStrategy) and self.mapping.label_pads:
            self._configure_momentary_mode_for_no_feedback()

        self._setup_callbacks()
        self._setup_napari_events()

        # Initialize from current state
        self._update_slice_range()
        self._check_active_layer()

    def _setup_callbacks(self) -> None:
        """Register callbacks for mapped controls."""
        if self.mapping.coarse_slice:
            self.midi_controller.on_control(self.mapping.coarse_slice, self._on_coarse_change)
        if self.mapping.fine_slice:
            self.midi_controller.on_control(self.mapping.fine_slice, self._on_fine_change)
        if self.mapping.zoom:
            self.midi_controller.on_control(self.mapping.zoom, self._on_zoom_change)
        if self.mapping.brush_size:
            self.midi_controller.on_control(self.mapping.brush_size, self._on_brush_change)

        # Register pad callbacks for label selection
        for i, pad_id in enumerate(self.mapping.label_pads):
            self.midi_controller.on_control(
                pad_id,
                lambda state, idx=i: self._on_label_select(state, idx),
            )

        # Navigation buttons for slice stepping
        if self.mapping.slice_up:
            self.midi_controller.on_control(self.mapping.slice_up, self._on_slice_up)
        if self.mapping.slice_down:
            self.midi_controller.on_control(self.mapping.slice_down, self._on_slice_down)

        # Navigation buttons for dimension rolling
        if self.mapping.roll_left:
            self.midi_controller.on_control(self.mapping.roll_left, self._on_roll_left)
        if self.mapping.roll_right:
            self.midi_controller.on_control(self.mapping.roll_right, self._on_roll_right)

        # Transport buttons for undo/redo
        if self.mapping.undo:
            self.midi_controller.on_control(self.mapping.undo, self._on_undo)
        if self.mapping.redo:
            self.midi_controller.on_control(self.mapping.redo, self._on_redo)

    def _setup_napari_events(self) -> None:
        """Connect to napari layer events."""
        self.viewer.layers.events.inserted.connect(self._on_layer_inserted)
        self.viewer.layers.selection.events.changed.connect(self._on_selection_changed)
        self.viewer.dims.events.order.connect(self._on_dims_order_changed)

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
        """Calculate target slice from coarse + fine values.

        Coarse control always spans the full 0 to max_slices range.
        At coarse extremes (0 or 127), the exact endpoint is returned.
        Fine control adds ±64 slice offset for intermediate positions.
        """
        if self.max_slices <= 0:
            return 0

        # Coarse extremes always return exact endpoints
        if self.coarse_value == 0:
            return 0
        if self.coarse_value == 127:
            return self.max_slices

        # Coarse: full range 0 to max_slices
        base_slice = int((self.coarse_value / 127) * self.max_slices)

        # Fine: ±64 slice offset, centered at 64
        offset = self.fine_value - 64

        return max(0, min(self.max_slices, base_slice + offset))

    def _update_viewer_slice(self) -> None:
        """Apply computed slice to napari viewer."""
        if self.max_slices <= 0:
            return
        target_slice = self._compute_slice()
        self.viewer.dims.set_current_step(self.slice_axis, target_slice)

    def _update_slice_range(self) -> None:
        """Update max_slices based on largest layer along slice axis.

        Scans all Image/Labels layers to find the maximum dimension
        along the current slice axis, rather than using only the active layer.
        """
        max_dim = 0

        for layer in self.viewer.layers:
            if not isinstance(layer, (napari.layers.Image, napari.layers.Labels)):
                continue
            if layer.data.ndim < 3:
                continue
            # Get dimension along slice axis (handle case where layer has fewer dims)
            if self.slice_axis < layer.data.ndim:
                dim_size = layer.data.shape[self.slice_axis]
                max_dim = max(max_dim, dim_size)

        if max_dim > 0:
            self.max_slices = max_dim - 1

    # --- Slice stepping (button navigation) ---

    def _on_slice_up(self, state: ControlState) -> None:
        """Move slice +1 on button press."""
        if state.value == 0:  # Ignore button release
            return
        if self.max_slices <= 0:
            return
        current = self.viewer.dims.current_step[self.slice_axis]
        new_step = min(current + 1, self.max_slices)
        self.viewer.dims.set_current_step(self.slice_axis, new_step)

    def _on_slice_down(self, state: ControlState) -> None:
        """Move slice -1 on button press."""
        if state.value == 0:  # Ignore button release
            return
        if self.max_slices <= 0:
            return
        current = self.viewer.dims.current_step[self.slice_axis]
        new_step = max(current - 1, 0)
        self.viewer.dims.set_current_step(self.slice_axis, new_step)

    # --- Dimension rolling ---

    def _on_roll_left(self, state: ControlState) -> None:
        """Roll dimensions left on button press."""
        if state.value == 0:  # Ignore button release
            return
        self._roll_dims(direction=-1)

    def _on_roll_right(self, state: ControlState) -> None:
        """Roll dimensions right on button press."""
        if state.value == 0:  # Ignore button release
            return
        self._roll_dims(direction=1)

    def _roll_dims(self, direction: int) -> None:
        """Roll dimension order (cycles XY -> YZ -> XZ views).

        Args:
            direction: -1 for left roll, +1 for right roll.
        """
        current_order = list(self.viewer.dims.order)
        ndims = len(current_order)

        if ndims < 3:
            return  # Nothing to roll for 2D data

        if direction > 0:
            # Roll right: last element moves to front
            new_order = [current_order[-1]] + current_order[:-1]
        else:
            # Roll left: first element moves to end
            new_order = current_order[1:] + [current_order[0]]

        # Setting order triggers _on_dims_order_changed which updates slice_axis
        self.viewer.dims.order = tuple(new_order)

    def _on_dims_order_changed(self, event) -> None:
        """Handle dimension order changes (from napari UI or MIDI roll buttons)."""
        order = list(self.viewer.dims.order)
        if len(order) < 3:
            return
        self.slice_axis = order[0]
        self._update_slice_range()

    # --- Undo/Redo ---

    def _on_undo(self, state: ControlState) -> None:
        """Trigger undo on the active Labels layer."""
        if state.value == 0:  # Ignore button release
            return
        if self._labels_layer is None:
            return
        self._labels_layer.undo()

    def _on_redo(self, state: ControlState) -> None:
        """Trigger redo on the active Labels layer."""
        if state.value == 0:  # Ignore button release
            return
        if self._labels_layer is None:
            return
        self._labels_layer.redo()

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
        brush_size = self.MIN_BRUSH_SIZE * ((self.MAX_BRUSH_SIZE / self.MIN_BRUSH_SIZE) ** normalized)
        self._labels_layer.brush_size = int(brush_size)

    # --- Label selection ---

    def _on_label_select(self, state: ControlState, label_index: int) -> None:
        """Handle pad press - select the corresponding label.

        If the layer defines padbound_actions in its metadata, mapped indices
        trigger the action callback instead of changing selected_label.
        """
        if self._labels_layer is None:
            return

        # Check for custom layer actions (generic hook for any plugin)
        actions = getattr(self._labels_layer, "metadata", {}).get(
            "padbound_actions", {}
        )
        if label_index in actions:
            if state.value > 0:  # Only trigger on press, not release
                actions[label_index]()
            self._update_label_feedback()
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

    def _connect_layer_events(self, layer: napari.layers.Labels) -> None:
        """Connect to a Labels layer's events."""
        layer.events.colormap.connect(self._on_colormap_changed)
        layer.events.selected_label.connect(self._on_selected_label_changed)

    def _disconnect_layer_events(self, layer: napari.layers.Labels) -> None:
        """Disconnect from a Labels layer's events."""
        layer.events.colormap.disconnect(self._on_colormap_changed)
        layer.events.selected_label.disconnect(self._on_selected_label_changed)

    def _on_colormap_changed(self, event) -> None:
        """Handle colormap changes - update pad colors."""
        self._update_label_feedback()

    def _on_selected_label_changed(self, event) -> None:
        """Handle selected label changes from napari UI - update pad feedback."""
        self._update_label_feedback()

    def _get_label_colors(self) -> list[str]:
        """Get hex colors for labels from the active layer."""
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

        # Disconnect from previous layer's events (if any)
        if self._labels_layer is not None:
            self._disconnect_layer_events(self._labels_layer)

        self._labels_layer = layer

        # Connect to new layer's events
        self._connect_layer_events(layer)

        # Initial update
        label_colors = self._get_label_colors()
        selected = layer.selected_label
        self.label_feedback.update_feedback(selected, label_colors)

    # --- No-feedback controller configuration ---

    def _configure_momentary_mode_for_no_feedback(self) -> None:
        """Configure controller pads to MOMENTARY mode when no LED feedback available.

        Controllers without LED feedback (like Xjam) work better with MOMENTARY pads
        because we cannot programmatically turn off toggle pads - users would have to
        manually press each pad again to deselect.
        """
        if not self.midi_controller.is_connected:
            return

        # Extract unique bank IDs from the control definitions
        controls = self.midi_controller.get_controls()
        bank_ids = list({c.bank_id for c in controls if c.bank_id is not None})

        if not bank_ids:
            # Fallback for controllers without explicit bank definitions
            bank_ids = ["bank_1"]

        # Build config with toggle_mode=False for all banks
        # Controllers like Xjam apply this globally to all pads
        banks = {bank_id: BankConfig(controls={}, toggle_mode=False) for bank_id in bank_ids}

        try:
            config = ControllerConfig(banks=banks)
            self.midi_controller.reconfigure(config, update_in_memory_only=False)
            logger.info("Configured pads to MOMENTARY mode (no LED feedback available)")
        except Exception as e:
            logger.warning(f"Could not configure MOMENTARY mode: {e}")
