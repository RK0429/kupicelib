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
# Name:        qspice_simulator.py
# Purpose:     Represents QSPICE
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     26-08-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from ..sim.simulator import (
    Simulator,
    SpiceSimulatorError,
    StdStream,
    run_function,
)

_logger = logging.getLogger("kupicelib.QSpiceSimulator")


class Qspice(Simulator):
    """Stores the simulator location and command line options, and runs simulations."""

    raw_extension = ".qraw"
    """:meta private:"""

    _spice_exe_win_paths: ClassVar[list[str]] = [
        "~/Qspice/QSPICE64.exe",
        "~/AppData/Local/Programs/Qspice/QSPICE64.exe",
        "C:/Program Files/QSPICE/QSPICE64.exe",
    ]

    _default_lib_paths: ClassVar[list[str]] = [
        "C:/Program Files/QSPICE",
        "~/Documents/QSPICE",
    ]

    _detected_executable: list[str]
    if sys.platform in {"linux", "darwin"}:
        # Status mid-2024: QSPICE offers limited support under Linux+Wine and
        # none for macOS+Wine. Leave the executable unset for now.
        _detected_executable = []
    else:
        _detected_executable = []
        for candidate in _spice_exe_win_paths:
            normalized = (
                os.path.expanduser(candidate) if candidate.startswith("~") else candidate
            )
            if os.path.exists(normalized):
                _detected_executable = [normalized]
                break

    spice_exe: ClassVar[list[str]] = _detected_executable
    process_name: str = (
        Simulator.guess_process_name(spice_exe[0]) if spice_exe else ""
    )
    if spice_exe:
        _logger.debug("Found Qspice installed in: '%s'", spice_exe)

    qspice_args: ClassVar[dict[str, list[str]]] = {
        "-ASCII": ["-ASCII"],
        "-ascii": ["-ASCII"],
        "-binary": ["-binary"],
        "-BSIM1": ["-BSIM1"],
        "-Meyer": ["-Meyer"],
        "-o": ["-o", "<path>"],
        "-ProtectSelections": ["-ProtectSelections", "<path>"],
        "-ProtectSubcircuits": ["-ProtectSubcircuits", "<path>"],
        "-r": ["-r", "<path>"],
    }
    """:meta private:"""

    _default_run_switches: ClassVar[list[str]] = ["-o"]

    @classmethod
    def valid_switch(
        cls, switch: str, switch_param: str | Sequence[str] | None = None
    ) -> list[str]:
        """Validate and format a QSPICE command-line switch."""

        if isinstance(switch_param, Sequence) and not isinstance(switch_param, str):
            parameter = " ".join(str(part) for part in switch_param)
        else:
            parameter = str(switch_param).strip() if switch_param is not None else ""
        switch_clean = switch.strip()
        if not switch_clean:
            return []
        if not switch_clean.startswith("-"):
            switch_clean = "-" + switch_clean

        if switch_clean in cls._default_run_switches:
            _logger.info("Switch %s is already in the default switches", switch_clean)
            return []

        if switch_clean in cls.qspice_args:
            return [value.replace("<path>", parameter) for value in cls.qspice_args[switch_clean]]
        raise ValueError(f"Invalid Switch '{switch_clean}'")

    @classmethod
    def run(
        cls,
        netlist_file: str | Path,
        cmd_line_switches: Sequence[str] | str | None = None,
        timeout: float | None = None,
        stdout: StdStream = None,
        stderr: StdStream = None,
        exe_log: bool = False,
    ) -> int:
        """Execute a QSPICE simulation run."""

        if not cls.is_available():
            _logger.error("================== ALERT! ====================")
            _logger.error("Unable to find the QSPICE executable.")
            _logger.error("A specific location of the QSPICE can be set")
            _logger.error("using the create_from(<location>) class method")
            _logger.error("==============================================")
            raise SpiceSimulatorError("Simulator executable not found.")

        if cmd_line_switches is None:
            switches_list: list[str] = []
        elif isinstance(cmd_line_switches, str):
            switches_list = [cmd_line_switches]
        else:
            switches_list = list(cmd_line_switches)
        netlist_path = Path(netlist_file)

        logfile = netlist_path.with_suffix(".log").as_posix()
        rawfile = netlist_path.with_suffix(".qraw").as_posix()

        cmd_run = (
            cls.spice_exe
            + switches_list
            + ["-Run"]
            + ["-o", logfile]
            + ["-r", rawfile]
            + [netlist_path.as_posix()]
        )

        if exe_log:
            log_exe_file = netlist_path.with_suffix(".exe.log")
            with open(log_exe_file, "w", encoding="utf-8") as outfile:
                return run_function(
                    cmd_run,
                    timeout=timeout,
                    stdout=outfile,
                    stderr=subprocess.STDOUT,
                )
        return run_function(cmd_run, timeout=timeout, stdout=stdout, stderr=stderr)
