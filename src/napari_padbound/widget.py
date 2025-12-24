"""napari-padbound widget for MIDI controller integration."""

from padbound import Controller, ControllerConfig, BankConfig, ControlConfig, ControlType
from padbound.plugins.akai_lpd8_mk2 import AkaiLPD8MK2Plugin
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

from napari_padbound.label_controller import LabelPaletteController
from napari_padbound.slice_controller import MidiSliceController


def create_midi_config() -> ControllerConfig:
    """Create MIDI controller configuration with momentary pads.

    Returns:
        ControllerConfig for AKAI LPD8 with momentary pad mode.
    """
    return ControllerConfig(
        banks={
            "bank_1": BankConfig(
                toggle_mode=False,  # MOMENTARY mode for all pads
                controls={
                    "pad_1": ControlConfig(type=ControlType.MOMENTARY, color="white"),
                    "pad_2": ControlConfig(type=ControlType.MOMENTARY),
                    "pad_3": ControlConfig(type=ControlType.MOMENTARY),
                    "pad_4": ControlConfig(type=ControlType.MOMENTARY),
                    "pad_5": ControlConfig(type=ControlType.MOMENTARY),
                    "pad_6": ControlConfig(type=ControlType.MOMENTARY),
                    "pad_7": ControlConfig(type=ControlType.MOMENTARY),
                    "pad_8": ControlConfig(type=ControlType.MOMENTARY),
                },
            ),
        },
    )


class PadboundWidget(QWidget):
    """Main widget for the napari-padbound plugin.

    Provides MIDI control via AKAI LPD8 controller:
    - Knob 1: Coarse slice control (full range)
    - Knob 2: Brush size (logarithmic 1-100)
    - Knob 5: Fine slice control (+/- 64 slices)
    - Pad 1: Eraser (label 0, white LED)
    - Pads 2-8: Labels 1-7 (colors from colormap)
    """

    POLL_INTERVAL_MS = 10  # 100Hz polling rate

    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer

        # Controllers
        self._midi_controller: Controller | None = None
        self._slice_controller: MidiSliceController | None = None
        self._label_controller: LabelPaletteController | None = None
        self._timer: QTimer | None = None

        # Setup UI
        self.setLayout(QVBoxLayout())

        self.status_label = QLabel()
        self.layout().addWidget(self.status_label)

        self.info_label = QLabel(
            "Controls:\n"
            "  Knob 1: Coarse slice (full range)\n"
            "  Knob 2: Brush size\n"
            "  Knob 5: Fine slice (+/- 64)\n"
            "  Knob 6: Zoom (0.1x-10x)\n"
            "\n"
            "  Pad 1: Eraser\n"
            "  Pads 2-8: Labels 1-7"
        )
        self.layout().addWidget(self.info_label)

        # Initialize controllers
        self._init_controllers()

    def _init_controllers(self) -> None:
        """Initialize the MIDI controller and feature controllers."""
        try:
            # Create shared MIDI controller with configuration
            config = create_midi_config()
            self._midi_controller = Controller(
                plugin=AkaiLPD8MK2Plugin(),
                config=config,
                auto_connect=True,
            )

            # Create feature controllers sharing the MIDI controller
            self._slice_controller = MidiSliceController(
                self.viewer, self._midi_controller
            )
            self._label_controller = LabelPaletteController(
                self.viewer, self._midi_controller
            )

            # Start MIDI event polling
            self._start_event_loop()

            self._update_status()
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def _start_event_loop(self) -> None:
        """Start Qt timer for periodic MIDI event processing."""
        self._timer = QTimer()
        self._timer.timeout.connect(self._process_midi)
        self._timer.start(self.POLL_INTERVAL_MS)

    def _process_midi(self) -> None:
        """Process pending MIDI events."""
        if self._midi_controller and self._midi_controller.is_connected:
            self._midi_controller.process_events()

    def _update_status(self) -> None:
        """Update the connection status display."""
        if self._midi_controller and self._midi_controller.is_connected:
            self.status_label.setText("MIDI Controller: Connected")
        else:
            self.status_label.setText("MIDI Controller: Disconnected")

    def closeEvent(self, event) -> None:
        """Clean up when widget is closed."""
        if self._timer:
            self._timer.stop()
            self._timer = None

        if self._midi_controller:
            self._midi_controller.disconnect()
            self._midi_controller = None

        super().closeEvent(event)
