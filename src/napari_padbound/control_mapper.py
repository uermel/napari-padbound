"""Control mapping for auto-discovering and assigning MIDI controls to features."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from padbound import Controller
    from padbound.controls import ControlDefinition


class ControlMapping(BaseModel):
    """Mapping of physical controls to napari features."""

    coarse_slice: str | None = None  # control_id for coarse slice
    fine_slice: str | None = None  # control_id for fine slice
    zoom: str | None = None  # control_id for zoom
    brush_size: str | None = None  # control_id for brush size
    label_pads: list[str] = Field(default_factory=list)  # control_ids for labels

    # Navigation button mappings
    slice_up: str | None = None  # +1 slice step
    slice_down: str | None = None  # -1 slice step
    roll_left: str | None = None  # Roll dims left
    roll_right: str | None = None  # Roll dims right

    # Transport button mappings
    undo: str | None = None  # Undo action (stop button)
    redo: str | None = None  # Redo action (play button)


class ControlMapper:
    """Discovers and maps controller controls to napari features.

    Automatically assigns controls based on their type and capabilities:
    - Faders preferred for coarse slice control
    - Knobs/encoders for fine slice, brush size, zoom
    - Pads for label selection
    """

    def __init__(self, controller: Controller) -> None:
        """Initialize the control mapper.

        Args:
            controller: The padbound Controller instance.
        """
        self.controller = controller
        self.controls: list[ControlDefinition] = controller.get_controls()

    def create_mapping(self) -> ControlMapping:
        """Auto-discover and map controls based on capabilities.

        Priority for continuous controls: fader > knob > encoder
        All mapped controls come from the same bank (for multi-bank controllers).

        Returns:
            ControlMapping with assigned control IDs.
        """
        mapping = ControlMapping()

        # Group controls by category
        faders = [c for c in self.controls if c.category == "fader"]
        knobs = [c for c in self.controls if c.category == "knob"]
        encoders = [c for c in self.controls if c.category == "encoder"]
        pads = [c for c in self.controls if c.category == "pad"]

        # Determine primary bank from first fader (or first continuous control)
        all_continuous = faders + knobs + encoders
        primary_bank = all_continuous[0].bank_id if all_continuous else None

        # Filter to primary bank only (None matches None for bankless controllers)
        faders = [c for c in faders if c.bank_id == primary_bank]
        knobs = [c for c in knobs if c.bank_id == primary_bank]
        encoders = [c for c in encoders if c.bank_id == primary_bank]
        pads = [c for c in pads if c.bank_id == primary_bank]

        # Assign continuous controls (priority: fader > knob > encoder)
        continuous = faders + knobs + encoders
        if len(continuous) >= 1:
            mapping.coarse_slice = continuous[0].control_id
        if len(continuous) >= 2:
            mapping.fine_slice = continuous[1].control_id
        if len(continuous) >= 3:
            mapping.brush_size = continuous[2].control_id
        if len(continuous) >= 4:
            mapping.zoom = continuous[3].control_id

        # Assign pads for label selection
        mapping.label_pads = [p.control_id for p in pads]

        # Discover navigation buttons (for slice stepping and dim rolling)
        nav_controls = [c for c in self.controls if c.category == "navigation" and c.bank_id == primary_bank]
        for c in nav_controls:
            cid = c.control_id.lower()
            if cid in ("up", "nav_up") and mapping.slice_up is None:
                mapping.slice_up = c.control_id
            elif cid in ("down", "nav_down") and mapping.slice_down is None:
                mapping.slice_down = c.control_id
            elif cid in ("left", "nav_left") and mapping.roll_left is None:
                mapping.roll_left = c.control_id
            elif cid in ("right", "nav_right") and mapping.roll_right is None:
                mapping.roll_right = c.control_id

        # Discover transport buttons (for undo/redo)
        transport_controls = [c for c in self.controls if c.category == "transport" and c.bank_id == primary_bank]
        for c in transport_controls:
            cid = c.control_id.lower()
            if cid == "stop" and mapping.undo is None:
                mapping.undo = c.control_id
            elif cid == "play" and mapping.redo is None:
                mapping.redo = c.control_id

        return mapping

    def get_mapping_info(self) -> str:
        """Get human-readable description of the control mapping.

        Returns:
            Multi-line string describing the mapping.
        """
        mapping = self.create_mapping()
        lines = []

        if mapping.coarse_slice:
            lines.append(f"Coarse slice: {mapping.coarse_slice}")
        if mapping.fine_slice:
            lines.append(f"Fine slice: {mapping.fine_slice}")
        if mapping.brush_size:
            lines.append(f"Brush size: {mapping.brush_size}")
        if mapping.zoom:
            lines.append(f"Zoom: {mapping.zoom}")
        if mapping.label_pads:
            lines.append(f"Label pads: {len(mapping.label_pads)} pads")
        if mapping.slice_up:
            lines.append(f"Slice up: {mapping.slice_up}")
        if mapping.slice_down:
            lines.append(f"Slice down: {mapping.slice_down}")
        if mapping.roll_left:
            lines.append(f"Roll left: {mapping.roll_left}")
        if mapping.roll_right:
            lines.append(f"Roll right: {mapping.roll_right}")
        if mapping.undo:
            lines.append(f"Undo: {mapping.undo}")
        if mapping.redo:
            lines.append(f"Redo: {mapping.redo}")

        return "\n".join(lines) if lines else "No controls mapped"
