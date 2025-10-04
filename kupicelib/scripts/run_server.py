#!/usr/bin/env python

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Mapping, Sequence
from typing import cast

import keyboard

from kupicelib.client_server.sim_server import SimServer
from kupicelib.sim.simulator import Simulator
from kupicelib.simulators.ltspice_simulator import LTspice
from kupicelib.simulators.ngspice_simulator import NGspiceSimulator
from kupicelib.simulators.xyce_simulator import XyceSimulator

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        run_server.py
# Purpose:     A Command Line Interface to run the LTSpice Server
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     10-08-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

SIMULATOR_MAP: Mapping[str, type[Simulator]] = {
    "LTSpice": cast(type[Simulator], LTspice),
    "NGSpice": cast(type[Simulator], NGspiceSimulator),
    "XYCE": cast(type[Simulator], XyceSimulator),
}

def _resolve_simulator(name: str) -> type[Simulator]:
    try:
        return SIMULATOR_MAP[name]
    except KeyError as exc:
        raise ValueError(f"Simulator {name} is not supported") from exc


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the LTSpice server. This CLI wraps SimServer to execute "
            "simulations in parallel via a server-client architecture. "
            "Specify the simulator to use (LTSpice, NGSpice, XYCE, etc.)."
        )
    )
    parser.add_argument(
        "simulator",
        type=str,
        default="LTSpice",
        help="Simulator to be used (LTSpice, NGSpice, XYCE, etc.)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=9000,
        help="Port to run the server. Default is 9000",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=".",
        help="Output folder for the results. Default is the current folder",
    )
    parser.add_argument(
        "-l",
        "--parallel",
        type=int,
        default=4,
        help="Maximum number of parallel simulations. Default is 4",
    )
    parser.add_argument(
        "timeout",
        type=int,
        default=300,
        help="Timeout for the simulations. Default is 300 seconds (5 minutes)",
    )

    raw_args = list(argv)[1:] if argv is not None else None

    if (argv is None and len(sys.argv) == 1) or (argv is not None and not raw_args):
        parser.print_help(sys.stderr)
        raise SystemExit(1)

    return parser.parse_args(raw_args)


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    parallel = max(args.parallel, 1)

    simulator_cls = _resolve_simulator(args.simulator)

    server = SimServer(
        simulator_cls,
        parallel_sims=parallel,
        output_folder=args.output,
        port=args.port,
        timeout=args.timeout,
    )
    print("Server Started. Press and hold 'q' to stop")
    while server.running():
        time.sleep(0.2)
        if keyboard.is_pressed("q"):
            server.stop_server()
            break


if __name__ == "__main__":
    import logging

    log1 = logging.getLogger("kupicelib.ServerSimRunner")
    log2 = logging.getLogger("kupicelib.SimServer")
    log3 = logging.getLogger("kupicelib.SimRunner")
    log4 = logging.getLogger("kupicelib.RunTask")
    log1.setLevel(logging.INFO)
    log2.setLevel(logging.INFO)
    log3.setLevel(logging.INFO)
    log4.setLevel(logging.INFO)
    main()
