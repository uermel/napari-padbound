"""MIDI Slice Controller for napari using padbound library."""

from __future__ import annotations

from typing import TYPE_CHECKING

import napari

if TYPE_CHECKING:
    from padbound import Controller
    from padbound.controls import ControlState


class MidiSliceController:
    """Controls napari slice navigation and zoom via AKAI LPD8 MIDI controller.

    Uses three knobs:
    - Coarse knob (knob_1): Maps 0-127 to full slice range
    - Fine knob (knob_5): Provides +/- 64 slice offset from coarse value
    - Zoom knob (knob_6): Logarithmic zoom from 0.1x to 10x
    """

    COARSE_KNOB = "knob_1@bank_1"
    FINE_KNOB = "knob_5@bank_1"
    ZOOM_KNOB = "knob_6@bank_1"

    MIN_ZOOM = 0.1
    MAX_ZOOM = 10.0

    def __init__(self, viewer: napari.Viewer, midi_controller: Controller) -> None:
        """Initialize the MIDI slice controller.

        Args:
            viewer: The napari viewer instance to control.
            midi_controller: Shared padbound Controller instance.
        """
        self.viewer = viewer
        self.midi_controller = midi_controller

        # Slice navigation state
        self.max_slices = 0
        self.slice_axis = 0  # Typically axis 0 for 3D stacks (ZYX)

        # Knob value tracking
        self.coarse_value = 0  # 0-127, maps to full slice range
        self.fine_value = 64  # 0-127, center at 64 (no offset)

        # Setup components
        self._setup_knob_callbacks()
        self._setup_napari_events()

        # Initialize slice range from current active layer
        self._update_slice_range()

    def _setup_knob_callbacks(self) -> None:
        """Register callbacks for slice and zoom control knobs."""
        self.midi_controller.on_control(self.COARSE_KNOB, self._on_coarse_change)
        self.midi_controller.on_control(self.FINE_KNOB, self._on_fine_change)
        self.midi_controller.on_control(self.ZOOM_KNOB, self._on_zoom_change)

    def _setup_napari_events(self) -> None:
        """Connect to napari layer events."""
        self.viewer.layers.events.inserted.connect(self._on_layer_inserted)
        self.viewer.layers.selection.events.changed.connect(self._on_selection_changed)

    def _on_coarse_change(self, state: ControlState) -> None:
        """Handle coarse knob rotation.

        Args:
            state: The control state containing the new value.
        """
        self.coarse_value = state.value
        self._update_viewer_slice()

    def _on_fine_change(self, state: ControlState) -> None:
        """Handle fine knob rotation.

        Args:
            state: The control state containing the new value.
        """
        self.fine_value = state.value
        self._update_viewer_slice()

    def _on_zoom_change(self, state: ControlState) -> None:
        """Handle zoom knob rotation - logarithmic mapping 0.1x to 10x.

        Args:
            state: The control state containing the new value.
        """
        # Logarithmic mapping: normalized (0-1) → zoom (0.1-10)
        # Formula: zoom = min * (max/min)^normalized
        normalized = state.normalized_value
        zoom = self.MIN_ZOOM * ((self.MAX_ZOOM / self.MIN_ZOOM) ** normalized)
        self.viewer.camera.zoom = zoom

    def _compute_slice(self) -> int:
        """Calculate target slice from coarse + fine values.

        Returns:
            The target slice index, clamped to valid range.
        """
        # Coarse: map 0-127 to full slice range
        if self.max_slices > 0:
            base_slice = int((self.coarse_value / 127) * self.max_slices)
        else:
            base_slice = 0

        # Fine: center at 64, so 0=-64 offset, 127=+63 offset
        offset = self.fine_value - 64

        # Clamp to valid range
        return max(0, min(self.max_slices, base_slice + offset))

    def _update_viewer_slice(self) -> None:
        """Apply computed slice to napari viewer."""
        if self.max_slices <= 0:
            return
        target_slice = self._compute_slice()
        self.viewer.dims.set_current_step(self.slice_axis, target_slice)

    def _on_layer_inserted(self, event) -> None:
        """Handle new layer insertion.

        Args:
            event: The layer insertion event.
        """
        # Update slice range - the new layer may become active
        self._update_slice_range()

    def _on_selection_changed(self, event) -> None:
        """Handle active layer selection change.

        Args:
            event: The selection change event.
        """
        self._update_slice_range()

    def _update_slice_range(self) -> None:
        """Update max_slices based on active layer."""
        active = self.viewer.layers.selection.active
        if active is None:
            return

        # Only handle Image and Labels layers
        if not isinstance(active, (napari.layers.Image, napari.layers.Labels)):
            return

        # Must be at least 3D
        if active.data.ndim < 3:
            return

        # Use first non-displayed dimension (axis 0 for typical ZYX stacks)
        self.slice_axis = 0
        self.max_slices = active.data.shape[self.slice_axis] - 1
