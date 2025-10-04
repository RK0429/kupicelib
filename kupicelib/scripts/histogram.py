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
# Name:        histogram.py
# Purpose:     Make an histogram plot based on data provided by the user
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     17-01-2017
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
"""This module uses matplotlib to plot a histogram of a gaussian distribution and
calculates the project n-sigma interval.

The data can either be retrieved from the clipboard or from a text file. Use the
following command line text to call this module.

.. code-block:: text

python -m kupicelib.Histogram [options] [data_file] TRACE

The help can be obtained by calling the script without arguments

.. code-block:: text

Usage: histogram.py [options] LOG_FILE TRACE

Options:   --version             show program's version number and exit   -h, --help
show this help message and exit   -s SIGMA, --sigma=SIGMA                         Sigma
to be used in the distribution fit. Default=3   -n NBINS, --nbins=NBINS Number of bins
to be used in the histogram. Default=20   -c FILTERS, --condition=FILTERS Filter
condition writen in python. More than one                         expression can be
added but each expression should be                         preceded by -c. EXAMPLE: -c
V(N001)>4 -c parameter==1                         -c  I(V1)<0.5   -f FORMAT,
--format=FORMAT                         Format string for the X axis. Example: -f %3.4f
-t TITLE, --title=TITLE                         Title to appear on the top of the
histogram.   -r RANGE, --range=RANGE                         Range of the X axis to use
for the histogram in the                         form min:max. Example: -r -1:1   -C,
--clipboard       If the data from the clipboard is to be used.   -i IMAGEFILE,
--image=IMAGEFILE                         Name of the image File. extension 'png'
"""
__author__ = "Nuno Canto Brum <me@nunobrum.com>"
__copyright__ = "Copyright 2017, Fribourg Switzerland"

import argparse
from typing import Any, cast

from kupicelib.log.logfile_data import ConvertibleValue, try_convert_value
from kupicelib.utils.detect_encoding import EncodingDetectError, detect_encoding


def main() -> None:
    import matplotlib.pyplot as plt
    import numpy as np
    from scipy.stats import norm  # type: ignore

    parser = argparse.ArgumentParser(
        prog="histogram.py",
        description=(
            "Plot a histogram for a trace in an LTspice log file or a list of values "
            "copied to the clipboard."
        ),
    )
    parser.add_argument("log_file", nargs="?", help="Path to the LTspice log file.")
    parser.add_argument("trace", nargs="?", help="Name of the trace to analyse.")
    parser.add_argument(
        "-s",
        "--sigma",
        type=int,
        default=3,
        help="Sigma to be used in the distribution fit. Default: 3",
    )
    parser.add_argument(
        "-n",
        "--nbins",
        type=int,
        default=20,
        help="Number of bins to be used in the histogram. Default: 20",
    )
    parser.add_argument(
        "-c",
        "--condition",
        dest="filters",
        action="append",
        default=[],
        help=(
            "Filter condition written in Python. Provide multiple expressions by "
            "repeating -c. Example: -c V(N001)>4 -c parameter==1 -c I(V1)<0.5\n"
            "Note: when parsing log files, the > and < operators are not supported."
        ),
    )
    parser.add_argument(
        "-f",
        "--format",
        dest="format",
        help="Format string for the X axis. Example: -f %3.4f",
    )
    parser.add_argument(
        "-t",
        "--title",
        dest="title",
        help="Title to appear on the top of the histogram.",
    )
    parser.add_argument(
        "-r",
        "--range",
        dest="range_expr",
        help=(
            "Range of the X axis to use for the histogram in the form min:max. "
            "Example: -r -1:1"
        ),
    )
    parser.add_argument(
        "-C",
        "--clipboard",
        action="store_true",
        dest="clipboard",
        help="Read newline-separated values from the clipboard instead of a log file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="imagefile",
        help=(
            "Output the image to a PNG file. Provide the output filename, e.g. -o image.png"
        ),
    )
    parser.add_argument(
        "-1",
        "--nonorm",
        dest="normalized",
        action="store_false",
        default=True,
        help="Disable histogram normalization so the bell curve area is not forced to 1.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1",
    )

    args = parser.parse_args()

    values: list[Any] = []

    trace_name: str
    logfile: str | None = None

    if args.clipboard:
        try:
            import clipboard  # type: ignore
        except ImportError:
            print("Failed to load clipboard package. Use PiP to install it.")
            exit(1)
        trace_name = args.trace or "var"
        text = clipboard.paste()
        for line in text.split("\n"):
            try:
                values.append(try_convert_value(line))
            except ValueError:
                print("Failed to convert line: '", line, "'")
    else:
        if args.log_file is None or args.trace is None:
            parser.print_help()
            parser.error(
                "Wrong number of parameters. Provide both the log file and the trace name"
            )
        logfile = args.log_file
        trace_name = args.trace
        assert logfile is not None
        assert trace_name is not None

        if args.filters:
            print("Filters Applied:", args.filters)
        else:
            print("No filters defined")

        if logfile.endswith(".log"):
            # Maybe it is a LTSpice log file
            from kupicelib.log.ltsteps import LTSpiceLogReader

            try:
                log = LTSpiceLogReader(logfile)
            except EncodingDetectError:
                print(
                    f"Failed to load file '{logfile}'. Use ltsteps first to convert to tlog format")
                exit(-1)
            else:
                if not args.filters:
                    values = log.get_measure_values_at_steps(trace_name, None)
                else:
                    step_filters: dict[str, Any] = {}
                    for expression in args.filters:
                        lhs_rhs = expression.split("==")
                        if len(lhs_rhs) == 2:
                            step_filters[lhs_rhs[0]] = try_convert_value(lhs_rhs[1])
                        else:
                            print(
                                "Unsupported comparison operator in reading .log files."
                            )
                            print(
                                "For enhanced comparators convert the file to tlog "
                                "using the ltsteps script"
                            )
                    selected_steps = log.steps_with_conditions(**step_filters)
                    values = log.get_measure_values_at_steps(
                        trace_name, selected_steps
                    )

        if len(values) == 0:
            encoding = detect_encoding(logfile)
            print(f"Loading file '{logfile}' with encoding '{encoding}'")
            with open(logfile, encoding=encoding) as log:
                header = log.readline().rstrip("\r\n")
                for sep in ["\t", ";", ","]:
                    if sep in header:
                        break
                else:
                    sep = None

                vars = header.split(sep)
                if len(vars) > 1:
                    try:
                        sav_col = vars.index(trace_name)
                    except ValueError:
                        print(f"File '{logfile}' doesn't have trace '{trace_name}'")
                        print(f"LOG FILE contains {vars}")
                        exit(-1)
                else:
                    sav_col = 0

                if not args.filters:
                    for line in log:
                        vs = line.split(sep)
                        values.append(try_convert_value(vs[sav_col]))
                else:
                    for line in log:
                        env = {
                            var: try_convert_value(value)
                            for var, value in zip(vars, line.split(sep), strict=False)
                        }

                        for expression in args.filters:
                            test = eval(expression, None, env)
                            if test is False:
                                break
                        else:
                            raw_val = env.get(trace_name)
                            if raw_val is None:
                                continue
                            converted = try_convert_value(
                                cast(ConvertibleValue, raw_val)
                            )
                            values.append(converted)

    if len(values) == 0:
        print("No elements found")
    elif len(values) < args.nbins:
        print(
            "Not enough elements for an histogram."
            f"Only found {len(values)} elements. Histogram is specified for {args.nbins} bins")
    else:
        x = np.array(values, dtype=float)
        mu = x.mean()
        mn = x.min()
        mx = x.max()
        sd = np.std(x)
        sigmin = mu - args.sigma * sd
        sigmax = mu + args.sigma * sd

        if args.range_expr is None:
            # Automatic calculation of the range
            axisXmin = mu - (args.sigma + 1) * sd
            axisXmax = mu + (args.sigma + 1) * sd

            if mn < axisXmin:
                axisXmin = mn

            if mx > axisXmax:
                axisXmax = mx
        else:
            try:
                smin, smax = args.range_expr.split(":")
                axisXmin = try_convert_value(smin)
                axisXmax = try_convert_value(smax)
            except (ValueError, TypeError):
                parser.error("Invalid range setting")
        fmt = args.format or "%f"
        format_spec = fmt.lstrip("%")

        def fmt_value(value: float | np.floating[Any]) -> str:
            return format(float(value), format_spec)

        print(f"Collected {len(values)} elements")
        print(f"Distributing in {args.nbins} bins")
        print(f"Minimum is {fmt_value(mn)}")
        print(f"Maximum is {fmt_value(mx)}")
        print(f"Mean is {fmt_value(mu)}")
        print(f"Standard Deviation is {fmt_value(sd)}")
        print(
            f"Sigma {args.sigma} boundaries are {fmt_value(sigmin)} "
            f"and {fmt_value(sigmax)}"
        )
        n, bins, _patches = plt.hist(
            x,
            args.nbins,
            density=args.normalized,
            facecolor="green",
            alpha=0.75,
            range=(axisXmin, axisXmax),
        )
        axisYmax = n.max() * 1.1

        if args.normalized:
            # add a 'best fit' line
            y = cast(np.ndarray, norm.pdf(bins, mu, sd))
            plt.plot(bins, y, "r--", linewidth=1)
            plt.axvspan(
                mu - args.sigma * sd,
                mu + args.sigma * sd,
                alpha=0.2,
                color="cyan",
            )
            plt.ylabel("Distribution [Normalised]")
        else:
            plt.ylabel("Distribution")
        plt.xlabel(trace_name)

        if args.title is None:
            title = (
                r"$\mathrm{Histogram\ of\ %s:}\ \mu="
                + fmt
                + r",\ stdev="
                + fmt
                + r",\ \sigma=%d$"
            ) % (trace_name, mu, sd, args.sigma)
        else:
            title = args.title
        plt.title(title)

        plt.axis([axisXmin, axisXmax, 0, axisYmax])
        plt.grid(True)
        if args.imagefile is not None:
            plt.savefig(args.imagefile)
        else:
            plt.show()


if __name__ == "__main__":
    main()
