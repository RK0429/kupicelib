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
# Name:        ngspice_simulator.py
# Purpose:     Tool used to launch NGspice simulations in batch mode.
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     23-02-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any, ClassVar

from ..sim.simulator import (
    Simulator,
    SpiceSimulatorError,
    StdStream,
    run_function,
)

_logger = logging.getLogger("kupicelib.NGSpiceSimulator")


class NGspiceSimulator(Simulator):
    """Stores the simulator location and command line options and runs simulations."""

    # Placed in order of preference. The first to be found will be used.
    _spice_exe_paths: ClassVar[list[str]] = [
        "C:/Apps/NGSpice64/bin/ngspice.exe",  # Windows
        "C:/Spice64/ngspice.exe",  # Windows, older style
        "/usr/local/bin/ngspice",  # MacOS and linux
        "ngspice",  # linux, when in path
    ]

    # the default lib paths, as used by get_default_library_paths
    # none
    _default_lib_paths: ClassVar[list[str]] = []

    # defaults:
    _detected_executable: ClassVar[list[str]] = []
    for candidate in _spice_exe_paths:
        normalized = os.path.expanduser(candidate) if candidate.startswith("~") else candidate
        if os.path.exists(normalized):
            _detected_executable = [normalized]
            break
        which_result = shutil.which(candidate)
        if which_result:
            _detected_executable = [which_result]
            break

    spice_exe: ClassVar[list[str]] = _detected_executable
    process_name: str = (
        Simulator.guess_process_name(spice_exe[0]) if spice_exe else ""
    )
    if spice_exe:
        _logger.debug("Found ngspice installed in: '%s'", spice_exe)

    ngspice_args: ClassVar[dict[str, list[str]]] = {
        # '-a'            : ['-a'],
        # '--autorun'     : ['--autorun'],  # run the loaded netlist
        # '-b'            : ['-b'],
        # '--batch'       : ['--batch'],  # process FILE in batch mode
        "-c": ["-c", "<FILE>"],  #
        "--circuitfile": ["--circuitfile", "<FILE>"],  # set the circuitfile
        "-D": ["-D", "var_value"],  #
        "--define": ["--define", "var_value"],  # define variable to true/[value]
        "-i": ["-i"],  #
        "--interactive": ["--interactive"],  # run in interactive mode
        "-n": ["-n"],  #
        "--no-spiceinit": [
            "--no-spiceinit"
        ],  # don't load the local or user's config file
        # '-o'            : ['-o', '<FILE>'],  #
        # '--output'      : ['--output', '<FILE>'],  # set the outputfile
        # '-p'            : ['-p'],  #
        # '--pipe'        : ['--pipe'],  # run in I/O pipe mode
        "-q": ["-q"],  #
        "--completion": ["--completion"],  # activate command completion
        # '-r'            : ['-r'],  #
        # '--rawfile'     : ['--rawfile', '<FILE>'],  # set the rawfile output
        "--soa-log": ["--soa-log", "<FILE>"],  # set the outputfile for SOA warnings
        "-s": ["-s"],  #
        "--server": ["--server"],  # run spice as a server process
        "-t": ["-t", "<TERM>"],  #
        "--term": ["--term", "<TERM>"],  # set the terminal type
        # '-h'            : ['-h'],  #
        # '--help'        : ['--help'],  # display this help and exit
        # '-v'            : ['-v'],  #
        # '--version'     : ['--version'],  # output version information and exit
    }
    """:meta private:"""

    _default_run_switches: ClassVar[list[str]] = ["-b", "-o", "-r", "-a"]
    _compatibility_mode = "kiltpsa"

    @classmethod
    def valid_switch(cls, switch: str, switch_param: Any = "") -> list[str]:
        """Validates a command line switch. The following options are available for
        NGSpice:

        * `-c, --circuitfile=FILE`: set the circuitfile * `-D,
        --define=variable[=value]`: define variable to true/[value] * `-n, --no-
        spiceinit`: don't load the local or user's config file * `-q, --completion`:
        activate command completion * `--soa-log=FILE`: set the outputfile for SOA
        warnings * `-s, --server`: run spice as a server process * `-t, --term=TERM`:
        set the terminal type

        The following parameters will already be filled in by kupicelib, and cannot be
        set:

        * `-a  --autorun`: run the loaded netlist * `-b, --batch`: process FILE in batch
        mode * `-o, --output=FILE`: set the outputfile * `-r, --rawfile=FILE`: set the
        rawfile output

        :param switch: switch to be added.
        :type switch: str
        :param parameter: parameter for the switch
        :type parameter: str, optional
        :return: the correct formatting for the switch
        :rtype: list
        """
        ret: list[str] = []  # This is an empty switch
        parameter = str(switch_param).strip() if switch_param is not None else ""

        switch_clean = switch.strip()
        if not switch_clean:
            return ret
        if not switch_clean.startswith("-"):
            switch_clean = "-" + switch_clean

        # will be set anyway?
        if switch_clean in cls._default_run_switches:
            _logger.info("Switch %s is already in the default switches", switch_clean)
            return []

        if switch_clean in cls.ngspice_args:
            if (
                cls._compatibility_mode
                and (switch_clean == "-D" or switch_clean == "--define")
                and parameter.lower().startswith("ngbehavior")
            ):
                _logger.info(
                    "Switch %s %s is already in the default switches. Use "
                    "'set_compatibility_mode' instead.",
                    switch_clean,
                    parameter,
                )
                return ret
            switch_list = cls.ngspice_args[switch_clean]
            if len(switch_list) == 2:
                param_token = switch_list[1]
                if (
                    param_token == "<FILE>"
                    or param_token == "<TERM>"
                    or (param_token == "var_value" and "=" in parameter)
                ):
                    ret = [switch_list[0], parameter]
                else:
                    _logger.warning(
                        "Invalid parameter %s for switch '%s'",
                        parameter,
                        switch_clean,
                    )
            else:
                ret = switch_list
        else:
            raise ValueError(f"Invalid Switch '{switch_clean}'")
        return ret

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
        """Executes a NGspice simulation run.

        A raw file and a log file will be generated, with the same name as the netlist
        file, but with `.raw` and `.log` extension.

        :param netlist_file: path to the netlist file
        :type netlist_file: Union[str, Path]
        :param cmd_line_switches: additional command line options. Best to have been
            validated by valid_switch(), defaults to None
        :type cmd_line_switches: list, optional
        :param timeout: If timeout is given, and the process takes too long, a
            TimeoutExpired exception will be raised, defaults to None
        :type timeout: float, optional
        :param stdout: control redirection of the command's stdout. Valid values are
            None, subprocess.PIPE, subprocess.DEVNULL, an existing file descriptor (a
            positive integer), and an existing file object with a valid file descriptor.
            With the default settings of None, no redirection will occur. Also see
            `exe_log` for a simpler form of control.
        :type stdout: _FILE, optional
        :param stderr: Like stdout, but affecting the command's error output. Also see
            `exe_log` for a simpler form of control.
        :type stderr: _FILE, optional
        :param exe_log: If True, stdout and stderr will be ignored, and the simulator's
            execution console messages will be written to a log file (named ...exe.log)
            instead of console. This is especially useful when running under wine or
            when running simultaneous tasks.
        :type exe_log: bool, optional
        :raises SpiceSimulatorError: when the executable is not found.
        :raises NotImplementedError: when the requested execution is not possible on
            this platform.
        :return: return code from the process
        :rtype: int
        """
        if not cls.is_available():
            _logger.error("================== ALERT! ====================")
            _logger.error("Unable to find the NGSPICE executable.")
            _logger.error("A specific location of the NGSPICE can be set")
            _logger.error("using the create_from(<location>) class method")
            _logger.error("==============================================")
            raise SpiceSimulatorError("Simulator executable not found.")

        # note: if you want ascii raw files, use "-D filetype=ascii"

        if cmd_line_switches is None:
            switches_list: list[str] = []
        elif isinstance(cmd_line_switches, str):
            switches_list = [cmd_line_switches]
        else:
            switches_list = list(cmd_line_switches)
        netlist_file = Path(netlist_file)

        logfile = netlist_file.with_suffix(".log").as_posix()
        rawfile = netlist_file.with_suffix(".raw").as_posix()
        extra_switches: list[str] = []
        if cls._compatibility_mode:
            extra_switches = ["-D", f"ngbehavior={cls._compatibility_mode}"]
        # TODO: -a seems useless with -b, however it is still defined in the
        # default switches. Need to check if it is really needed.
        cmd_run = (
            cls.spice_exe
            + switches_list
            + extra_switches
            + ["-b"]
            + ["-o"]
            + [logfile]
            + ["-r"]
            + [rawfile]
            + [netlist_file.as_posix()]
        )
        # start execution
        if exe_log:
            log_exe_file = netlist_file.with_suffix(".exe.log")
            with open(log_exe_file, "w") as outfile:
                error = run_function(
                    cmd_run, timeout=timeout, stdout=outfile, stderr=subprocess.STDOUT
                )
        else:
            error = run_function(cmd_run, timeout=timeout, stdout=stdout, stderr=stderr)
        return error

    @classmethod
    def set_compatibility_mode(cls, mode: str = _compatibility_mode):
        """Set the compatibility mode. It has become mandatory in recent ngspice
        versions, as the default 'all' is no longer valid.

        A good default seems to be "kiltpsa" (KiCad, LTspice, PSPICE, netlists).

        The following compatibility modes are available (as of end 2024, ngspice v44):

        * `a : complete netlist transformed` * `ps : PSPICE compatibility` * `hs :
        HSPICE compatibility` * `spe : Spectre compatibility` * `lt : LTSPICE
        compatibility` * `s3 : Spice3 compatibility` * `ll : all (currently not used)` *
        `ki : KiCad compatibility` * `eg : EAGLE compatibility` * `mc : for 'make
        check'`

        :param mode: the compatibility mode to be set. Set to None to remove the
            compatibility setting.
        :type mode: str
        """
        cls._compatibility_mode = mode
