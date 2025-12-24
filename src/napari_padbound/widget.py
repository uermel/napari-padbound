"""napari-padbound widget for MIDI controller integration."""

from padbound import Controller
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

from napari_padbound.viewer_controller import ViewerController


class PadboundWidget(QWidget):
    """Main widget for the napari-padbound plugin.

    Automatically detects any connected MIDI controller supported by padbound
    and maps available controls to napari features:
    - Coarse slice navigation (fader or knob)
    - Fine slice navigation (knob)
    - Brush size (knob)
    - Zoom (knob)
    - Label selection (pads)

    Features gracefully degrade based on controller capabilities.
    """

    POLL_INTERVAL_MS = 10  # 100Hz polling rate

    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer

        # Controllers
        self._midi_controller: Controller | None = None
        self._viewer_controller: ViewerController | None = None
        self._timer: QTimer | None = None
        self._cleanup_done = False

        # Setup UI
        self.setLayout(QVBoxLayout())

        self.status_label = QLabel()
        self.layout().addWidget(self.status_label)

        self.info_label = QLabel()
        self.layout().addWidget(self.info_label)

        # Connect to viewer close for proper cleanup
        # closeEvent is NOT called when napari shuts down, only when widget is closed
        self.viewer.window._qt_window.destroyed.connect(self._cleanup)

        # Initialize controllers
        self._init_controllers()

    def _init_controllers(self) -> None:
        """Initialize the MIDI controller and viewer controller."""
        try:
            # Auto-detect any connected controller
            self._midi_controller = Controller(plugin="auto", auto_connect=True)

            # Create unified viewer controller
            self._viewer_controller = ViewerController(
                self.viewer, self._midi_controller
            )

            # Start MIDI event polling
            self._start_event_loop()

            self._update_ui()
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            self.info_label.setText("No MIDI controller detected.\nConnect a supported controller and restart.")

    def _start_event_loop(self) -> None:
        """Start Qt timer for periodic MIDI event processing."""
        self._timer = QTimer()
        self._timer.timeout.connect(self._process_midi)
        self._timer.start(self.POLL_INTERVAL_MS)

    def _process_midi(self) -> None:
        """Process pending MIDI events."""
        if self._midi_controller and self._midi_controller.is_connected:
            self._midi_controller.process_events()

    def _update_ui(self) -> None:
        """Update the UI with controller info and mapping."""
        if self._midi_controller and self._midi_controller.is_connected:
            # Get controller name
            plugin_name = self._midi_controller.plugin.__class__.__name__
            self.status_label.setText(f"Controller: {plugin_name} (Connected)")

            # Show control mapping
            if self._viewer_controller:
                mapping_info = self._viewer_controller.mapping_info
                self.info_label.setText(f"Mapped controls:\n{mapping_info}")
        else:
            self.status_label.setText("MIDI Controller: Disconnected")
            self.info_label.setText("")

    def _cleanup(self) -> None:
        """Clean up resources when viewer is destroyed.

        This is connected to the viewer's Qt window destroyed signal,
        which fires when napari shuts down (unlike closeEvent which only
        fires when the dock widget is manually closed).
        """
        if self._cleanup_done:
            return
        self._cleanup_done = True

        if self._timer:
            self._timer.stop()
            self._timer = None

        if self._midi_controller:
            self._midi_controller.disconnect()
            self._midi_controller = None

    def closeEvent(self, event) -> None:
        """Clean up when widget is closed."""
        self._cleanup()
        super().closeEvent(event)
