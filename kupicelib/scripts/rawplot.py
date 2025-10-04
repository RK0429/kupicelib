#!/usr/bin/env python

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        rawplot.py
# Purpose:     Make a plot of the data in the raw file
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     02-09-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from kupicelib.raw.raw_read import RawRead

if TYPE_CHECKING:  # pragma: no cover - import heavy modules only for typing
    from matplotlib.axes import Axes
    from numpy.typing import NDArray

    from kupicelib.raw.raw_classes import TraceRead
else:  # pragma: no cover - fallbacks for runtime casts
    Axes = Any
    TraceRead = Any
    NDArray = Any


def _units_for_whattype(whattype: str) -> str | None:
    """Return a display unit for a LTSpice whattype descriptor."""

    whattype_lower = whattype.lower()
    if "voltage" in whattype_lower:
        return "V"
    if "current" in whattype_lower:
        return "A"
    return None


def main(argv: Sequence[str] | None = None) -> None:
    """Use matplotlib to plot the data stored in a LTSpice RAW file."""

    import sys

    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.axes import Axes
    from numpy import arange

    args = list(argv if argv is not None else sys.argv)

    if len(args) <= 1:
        print("Usage: rawplot.py RAW_FILE TRACE_NAME")
        print("TRACE_NAME is the trace to plot or omitted for all traces")
        sys.exit(-1)

    raw_filename = args[1]
    if len(args) > 2:
        requested_traces: Sequence[str] = args[2:]
        traces_argument: str | Sequence[str] = requested_traces
    else:
        requested_traces = []
        traces_argument = "*"

    matplotlib.use("tkagg")

    raw_reader = RawRead(raw_filename, traces_argument, verbose=True)
    for param, value in raw_reader.raw_params.items():
        padded_param = f"{param:<20}"
        print(f"{padded_param} {str(value).strip()}")

    if traces_argument == "*":
        print("Reading all the traces in the raw file")
        trace_names = raw_reader.get_trace_names()
    else:
        trace_names = list(requested_traces)

    traces = [cast(TraceRead, raw_reader.get_trace(trace)) for trace in trace_names]
    steps_data = raw_reader.get_steps() if raw_reader.axis is not None else [0]
    print("Steps read are :", list(steps_data))

    n_axis = len(traces)

    axis_tuple: Any
    fig, axis_tuple = plt.subplots(nrows=n_axis, ncols=1, sharex="all")
    if isinstance(axis_tuple, Axes):
        axes = [axis_tuple]
    else:
        axes = [cast(Axes, axis) for axis in axis_tuple]

    for index, trace in enumerate(traces):
        ax = axes[index]
        ax.grid(True)
        if "log" in raw_reader.flags:
            ax.set_xscale("log")
        for step_index in steps_data:
            if raw_reader.axis is not None:
                x_values = raw_reader.get_axis(step_index)
            else:
                x_values = arange(raw_reader.nPoints)
            y_values = trace.get_wave(step_index)
            y_array = np.asarray(y_values)
            label = f"{trace.name}:{step_index}"
            if "complex" in raw_reader.flags:
                x_plot = np.abs(np.asarray(x_values))
                ax.set_yscale("log")
                magnitude = np.abs(y_array)
                ax.yaxis.label.set_color("blue")
                unit = _units_for_whattype(trace.whattype)
                ylabel = f"{label}(dB)" if unit is None else f"{label} ({unit})"
                ax.set(ylabel=ylabel)
                ax.plot(x_plot, magnitude)
                ax_phase = ax.twinx()
                y_complex = cast(NDArray[np.complexfloating[Any, Any]], y_array)
                ax_phase.plot(
                    x_plot,
                    np.angle(y_complex, deg=True),
                    color="red",
                    linestyle="-.",
                )
                ax_phase.yaxis.label.set_color("red")
                ax_phase.set(ylabel=f"{label} Phase (deg)")
            else:
                unit = _units_for_whattype(trace.whattype)
                ylabel = label if unit is None else f"{label} ({unit})"
                ax.plot(x_values, y_values)
                ax.set(ylabel=ylabel)
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
