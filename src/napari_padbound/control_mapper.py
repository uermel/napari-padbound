"""Control mapping for auto-discovering and assigning MIDI controls to features."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from padbound import Controller
    from padbound.controls import ControlDefinition


@dataclass
class ControlMapping:
    """Mapping of physical controls to napari features."""

    coarse_slice: str | None = None  # control_id for coarse slice
    fine_slice: str | None = None  # control_id for fine slice
    zoom: str | None = None  # control_id for zoom
    brush_size: str | None = None  # control_id for brush size
    label_pads: list[str] = field(default_factory=list)  # control_ids for labels


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

        Returns:
            ControlMapping with assigned control IDs.
        """
        mapping = ControlMapping()

        # Group controls by category
        faders = [c for c in self.controls if c.category == "fader"]
        knobs = [c for c in self.controls if c.category == "knob"]
        encoders = [c for c in self.controls if c.category == "encoder"]
        pads = [c for c in self.controls if c.category == "pad"]

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

        return "\n".join(lines) if lines else "No controls mapped"
