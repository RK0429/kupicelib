#!/usr/bin/env python

import logging
import os

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        ltspice_simulator.py
# Purpose:     Represents a LTspice tool and it's command line options
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     23-12-2016
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from ..sim.simulator import Simulator, SpiceSimulatorError, StdStream, run_function

_logger = logging.getLogger("kupicelib.LTSpiceSimulator")


class LTspice(Simulator):
    """Stores the simulator location and command line options and is responsible for
    generating netlists and running simulations.

    Searches on the any usual locations for a simulator.
    """
    # windows paths (that are also valid for wine)
    # Please note that os.path.expanduser and os.path.join are sensitive to the style
    # of slash.
    # Placed in order of preference. The first to be found will be used.
    _spice_exe_win_paths: ClassVar[list[str]] = [
        "~/AppData/Local/Programs/ADI/LTspice/LTspice.exe",
        "~/Local Settings/Application Data/Programs/ADI/LTspice/LTspice.exe",
        "C:/Program Files/ADI/LTspice/LTspice.exe",
        "C:/Program Files/LTC/LTspiceXVII/XVIIx64.exe",
        "C:/Program Files (x86)/LTC/LTspiceXVII/XVIIx64.exe",
        "C:/Program Files (x86)/LTC/LTspiceIV/scad3.exe",
    ]

    # the default lib paths, as used by get_default_library_paths
    _default_lib_paths: ClassVar[list[str]] = [
        "~/AppData/Local/LTspice/lib",
        "~/Documents/LTspiceXVII/lib/",
        "~/Documents/LTspice/lib/",
        "~/My Documents/LTspiceXVII/lib/",
        "~/My Documents/LTspice/lib/",
        "~/Local Settings/Application Data/LTspice/lib",
    ]

    # defaults:
    spice_exe: ClassVar[list[str]] = []
    process_name = ""
    ltspice_args: ClassVar[dict[str, list[str]]] = {
        "-alt": ["-alt"],  # Set solver to Alternate.
        # Use ASCII.raw files. Seriously degrades program performance.
        "-ascii": ["-ascii"],
        "-big": ["-big"],  # Start as a maximized window.
        "-encrypt": ["-encrypt"],
        "-fastaccess": ["-FastAccess"],  # Convert raw file to FastAccess format.
        "-FixUpSchematicFonts": ["-FixUpSchematicFonts"],
        "-FixUpSymbolFonts": ["-FixUpSymbolFonts"],
        "-ini": ["-ini", "<path>"],  # Specify alternative LTspice.ini.
        "-I": ["-I<path>"],  # Insert library search path (last option).
        "-max": ["-max"],  # Synonym for -big
        "-netlist": ["-netlist"],  # Generate netlist from schematic.
        "-norm": ["-norm"],  # Set solver to Normal.
        "-PCBnetlist": ["-PCBnetlist"],  # Generate PCB format netlist.
        "-SOI": ["-SOI"],  # Allow up to 7 MOSFET nodes.
        "-sync": ["-sync"],  # Update component libraries.
    }
    _default_run_switches: ClassVar[list[str]] = ["-Run", "-b"]

    @classmethod
    def using_macos_native_sim(cls) -> bool:
        """Tells if the simulator used is the MacOS native LTspice.

        :return: True if the MacOS native LTspice is used, False otherwise (will also
            return False on Windows or Linux)
        :rtype: bool
        """
        return (
            sys.platform == "darwin"
            and bool(cls.spice_exe)
            and "wine" not in cls.spice_exe[0].lower()
        )

    @classmethod
    def valid_switch(
        cls, switch: str, switch_param: str | Sequence[str] | None = None
    ) -> list[str]:
        """Validate a command line switch.

        Available options for Windows/wine LTspice:
          - -alt: Set solver to Alternate.
          - -ascii: Use ASCII.raw files (slow!).
          - -encrypt: Encrypt a model library.
          - -fastaccess: Convert raw file to FastAccess format.
          - -FixUpSchematicFonts: Update old schematic text fonts.
          - -FixUpSymbolFonts: Update old symbol fonts.
          - -ini <path>: Specify alternative LTspice.ini file.
          - -I<path>: Insert library search path (last option).
          - -max: Start maximized (synonym for -big).
          - -netlist: Generate netlist from schematic.
          - -norm: Set solver to Normal.
          - -PCBnetlist: Generate PCB format netlist.
          - -SOI: Allow up to 7 MOSFET nodes.
          - -sync: Update component libraries.

        Always included (cannot be set):
          - -Run: Start simulation in batch mode.
          - -b: Batch mode.

        MacOS native LTspice supports only batch mode (-b).
        """

        # See if the MacOS simulator is used. If so, check if I use the native simulator
        if cls.using_macos_native_sim():
            # native LTspice has only '-b' switch
            raise ValueError(
                "MacOS native LTspice supports only batch mode ('-b')."
            )

        # format check
        switch = switch.strip()
        if len(switch) == 0:
            return []
        if switch[0] != "-":
            switch = "-" + switch

        # default run switches
        if switch in cls._default_run_switches:
            _logger.info(f"Switch {switch} is already in the default switches")
            return []

        if isinstance(switch_param, Sequence) and not isinstance(switch_param, str):
            parameter = " ".join(str(part) for part in switch_param)
        elif switch_param is None:
            parameter = ""
        else:
            parameter = str(switch_param)

        if switch in cls.ltspice_args:
            switches = cls.ltspice_args[switch]
            return [opt.replace("<path>", parameter) for opt in switches]
        else:
            valid_keys = ", ".join(sorted(cls.ltspice_args.keys()))
            raise ValueError(
                f"Invalid switch '{switch}'. "
                f"Valid switches are: {valid_keys}"
            )

    @classmethod
    def create_netlist(
        cls,
        asc_file: str | Path,
        cmd_line_switches: Sequence[str] | None = None,
        *,
        exe_log: bool | None = None,
    ) -> Path:
        """Generate a netlist from an LTspice schematic."""
        if not cls.spice_exe:
            cls.create_from(None)

        asc_path = Path(asc_file)
        if not asc_path.exists():
            raise FileNotFoundError(f"ASC file not found: {asc_path}")

        switches: list[str] = ["-netlist"]
        if cmd_line_switches:
            switches.extend(cmd_line_switches)

        command = [*cls.spice_exe, *switches, asc_path.as_posix()]
        if exe_log:
            _logger.info(
                "create_netlist ignores exe_log=%s; netlist generation does not emit logs",
                exe_log,
            )
        run_function(command)
        return asc_path.with_suffix(".net")





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
        """Execute a LTspice simulation in batch mode."""
        if not cls.is_available():
            _logger.error("================== ALERT! ====================")
            _logger.error("Unable to find a LTspice executable.")
            _logger.error("A specific location of the LTSPICE can be set")
            _logger.error("using the create_from(<location>) class method")
            _logger.error("==============================================")
            raise SpiceSimulatorError("Simulator executable not found.")

        if cmd_line_switches is None:
            cmd_switches: list[str] = []
        elif isinstance(cmd_line_switches, str):
            cmd_switches = [cmd_line_switches]
        else:
            cmd_switches = [str(option) for option in cmd_line_switches]

        netlist_path = Path(netlist_file)

        if sys.platform in {"linux", "darwin"}:
            if cls.using_macos_native_sim():
                if netlist_path.suffix.lower().endswith(".asc"):
                    raise NotImplementedError(
                        "MacOS native LTspice cannot run simulations on '.asc' files. "
                        "Simulate '.net' or '.cir' files or use LTspice under wine."
                    )
                cmd_run: list[str] = [
                    *cls.spice_exe,
                    "-b",
                    netlist_path.as_posix(),
                    *cmd_switches,
                ]
            else:
                cmd_run = [
                    *cls.spice_exe,
                    netlist_path.as_posix(),
                    *cmd_switches,
                ]
        elif sys.platform == "win32":
            cmd_run = [
                *cls.spice_exe,
                "-Run",
                "-b",
                netlist_path.as_posix(),
                *cmd_switches,
            ]
        else:
            raise NotImplementedError("Unsupported Platform for LTspice Simulator")

        if exe_log:
            exe_log_file = netlist_path.with_suffix(netlist_path.suffix + '.exe.log')
            with exe_log_file.open('w', encoding='utf-8') as exe_log_fd:
                return run_function(
                    cmd_run,
                    timeout=timeout,
                    stdout=exe_log_fd,
                    stderr=exe_log_fd,
                )

        return run_function(cmd_run, timeout=timeout, stdout=stdout, stderr=stderr)
    @classmethod
    def detect_executable(cls) -> None:
        """Detect and set spice_exe and process_name based on platform."""
        if sys.platform in ("linux", "darwin"):
            cls.detect_unix_executable()
        else:
            cls.detect_windows_executable()

    @classmethod
    def detect_unix_executable(cls) -> None:
        """Detect on Linux/Mac using wine and environment variables."""
        spice_folder = os.environ.get("LTSPICEFOLDER")
        spice_executable = os.environ.get("LTSPICEEXECUTABLE")
        if spice_folder and spice_executable:
            cls.spice_exe = ["wine", os.path.join(spice_folder, spice_executable)]
            cls.process_name = spice_executable
            return
        if spice_folder:
            cls.spice_exe = ["wine", os.path.join(spice_folder, "/XVIIx64.exe")]
            cls.process_name = "XVIIx64.exe"
            return
        if spice_executable:
            default_folder = os.path.expanduser(
                "~/.wine/drive_c/Program Files/LTC/LTspiceXVII"
            )
            cls.spice_exe = ["wine", os.path.join(default_folder, spice_executable)]
            cls.process_name = spice_executable
            return
        for exe in cls._spice_exe_win_paths:
            path = exe
            if path.startswith("~"):
                path = "C:/users/" + os.path.expandvars("${USER}" + path[1:])
            path = os.path.expanduser(path.replace("C:/", "~/.wine/drive_c/"))
            if os.path.exists(path):
                cls.spice_exe = ["wine", path]
                cls.process_name = cls.guess_process_name(path)
                return
        if sys.platform == "darwin":
            exe = "/Applications/LTspice.app/Contents/MacOS/LTspice"
            if os.path.exists(exe):
                cls.spice_exe = [exe]
                cls.process_name = cls.guess_process_name(exe)

    @classmethod
    def detect_windows_executable(cls) -> None:
        """Detect on Windows using default executable paths."""
        for exe in cls._spice_exe_win_paths:
            path = exe
            if path.startswith("~"):
                path = os.path.expanduser(path)
            if os.path.exists(path):
                cls.spice_exe = [path]
                cls.process_name = cls.guess_process_name(path)
                return


# initialize LTspice executable detection
LTspice.detect_executable()
_logger.debug(f"Found LTspice installed in: '{LTspice.spice_exe}'")
