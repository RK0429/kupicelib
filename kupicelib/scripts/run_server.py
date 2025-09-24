#!/usr/bin/env python

import argparse

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
import sys
import time

import keyboard

from kupicelib.client_server.sim_server import SimServer


def main():
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

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    if args.parallel < 1:
        args.parallel = 1

    if args.simulator == "LTSpice":
        from kupicelib.simulators.ltspice_simulator import LTspice

        simulator = LTspice
    elif args.simulator == "NGSpice":
        from kupicelib.simulators.ngspice_simulator import NGspiceSimulator

        simulator = NGspiceSimulator
    elif args.simulator == "XYCE":
        from kupicelib.simulators.xyce_simulator import XyceSimulator

        simulator = XyceSimulator
    else:
        raise ValueError(f"Simulator {args.simulator} is not supported")
        exit(-1)

    print("Starting Server")
    server = SimServer(
        simulator,
        parallel_sims=args.parallel,
        output_folder=args.output,
        port=args.port,
        timeout=args.timeout,
    )
    print("Server Started. Press and hold 'q' to stop")
    while server.running():
        time.sleep(0.2)
        # Check whether a key was pressed
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
