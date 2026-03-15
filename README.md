# napari-padbound

[![License BSD-3](https://img.shields.io/pypi/l/napari-padbound.svg?color=green)](https://github.com/uermel/napari-padbound/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/napari-padbound.svg?color=green)](https://pypi.org/project/napari-padbound)
[![Python Version](https://img.shields.io/pypi/pyversions/napari-padbound.svg?color=green)](https://python.org)
[![napari hub](https://img.shields.io/endpoint?url=https://api.napari-hub.org/shields/napari-padbound)](https://napari-hub.org/plugins/napari-padbound)

A [napari] plugin for controlling image annotation workflows with MIDI controllers via [padbound].

Use physical pads, knobs, faders, and buttons to navigate slices, select labels, adjust brush size, zoom, undo/redo, and more &mdash; with real-time LED feedback showing your current label colors on the controller.

## Features

- **Auto-detection** &mdash; Automatically finds and connects to any [padbound]-supported MIDI controller
- **Smart control mapping** &mdash; Automatically assigns available hardware controls to napari functions based on controller capabilities
- **Slice navigation** &mdash; Coarse and fine navigation through 3D+ data volumes via faders or knobs
- **Slice stepping** &mdash; Increment/decrement slices one at a time via navigation buttons
- **Zoom control** &mdash; Logarithmic zoom mapping (0.01x&ndash;10x) via knobs or faders
- **Brush size control** &mdash; Logarithmic brush size adjustment (1&ndash;100px) for label painting
- **Label selection** &mdash; Select labels by pressing pads; pad 1 is the eraser, remaining pads map to labels 1, 2, 3, ...
- **LED color feedback** &mdash; Pads display actual label colors from the napari colormap, with the selected label pulsing (on RGB-capable controllers)
- **Dimension rolling** &mdash; Cycle through dimension views (XY, YZ, XZ) via navigation buttons
- **Undo/redo** &mdash; Transport buttons for edit history on the active Labels layer
- **Graceful degradation** &mdash; Three feedback strategies (RGB color, binary toggle, none) adapt automatically to controller capabilities

## Supported Controllers

Any controller with a [padbound] plugin works automatically. Currently supported:

| Controller | Best for | Key controls |
|---|---|---|
| **AKAI APC mini MK2** | Full RGB feedback, many faders | 64 RGB pads, 9 faders, 17 buttons |
| **AKAI LPD8 MK2** | Compact RGB + knobs | 8 RGB pads, 8 knobs, 4 banks |
| **AKAI MPD218** | Velocity-sensitive pads | 16 pads, 6 encoders, 3 banks |
| **PreSonus ATOM** | RGB pads + encoders + buttons | 16 RGB pads, 4 encoders, 20 buttons |
| **Synido TempoPad P16** | RGB pads + transport | 16 RGB pads, 4 encoders, 6 buttons |
| **Behringer X-Touch Mini** | Encoders with LED rings | 16 pads, 8 encoders, 1 fader |
| **Xjam** | Budget option, multi-bank | 16 pads, 6 knobs, 3 banks |

## How Control Mapping Works

The plugin automatically discovers available controls and assigns them by priority:

**Continuous controls** (assigned in order: faders first, then knobs, then encoders):
1. First control &rarr; **Coarse slice** (full range of the data volume)
2. Second control &rarr; **Fine slice** (&plusmn;64 slices around the coarse position)
3. Third control &rarr; **Brush size** (logarithmic, 1&ndash;100px)
4. Fourth control &rarr; **Zoom** (logarithmic, 0.01x&ndash;10x)

**Pads** &rarr; **Label selection** (pad 1 = eraser, pad 2+ = labels)

**Navigation buttons** &rarr; Up/Down = slice step, Left/Right = dimension roll

**Transport buttons** &rarr; Stop = undo, Play = redo

The widget displays the detected controller and its mapped controls so you can see what each physical control does.

## Installation

```bash
pip install napari-padbound
```

For development:

```bash
git clone https://github.com/uermel/napari-padbound.git
cd napari-padbound
pip install -e ".[dev,testing]"
```

## Usage

1. Connect a supported MIDI controller via USB
2. Open [napari]
3. Go to **Plugins > padbound** to open the widget
4. Load a 3D image and create a Labels layer
5. Use your controller to navigate slices, select labels, and annotate

The widget shows the connected controller name and the mapping of physical controls to napari functions. If no controller is detected, the widget will indicate this.

## Development

```bash
# Linting
ruff check src/
ruff format src/
black src/

# Run tests
pytest
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Distributed under the terms of the [BSD-3] license, napari-padbound is free and open source software.

## Issues

If you encounter any problems, please [file an issue] along with a detailed description.

[napari]: https://github.com/napari/napari
[padbound]: https://github.com/uermel/padbound
[BSD-3]: http://opensource.org/licenses/BSD-3-Clause
[file an issue]: https://github.com/uermel/napari-padbound/issues
