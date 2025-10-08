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
# Name:        xyce_simulator.py
# Purpose:     Tool used to launch xyce simulations in batch mode.
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     14-03-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from ..sim.simulator import (
    Simulator,
    SpiceSimulatorError,
    StdStream,
    run_function,
)

_logger = logging.getLogger("kupicelib.XYCESimulator")


class XyceSimulator(Simulator):
    """Stores the simulator location and command line options and runs simulations."""

    # Placed in order of preference. The first to be found will be used.
    _spice_exe_paths: ClassVar[list[str]] = [
        "C:/Program Files/Xyce 7.9 NORAD/bin/xyce.exe",  # Windows
        "xyce",  # linux, when in path
    ]

    # the default lib paths, as used by get_default_library_paths
    # none
    _default_lib_paths: ClassVar[list[str]] = []

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
        _logger.debug("Found Xyce installed in: '%s'", spice_exe)

    xyce_args: ClassVar[dict[str, list[str]]] = {
        # '-b'                : ['-b'],  # batch mode flag for spice compatibility (ignored)
        # '-h'                : ['-h'],  # print usage and exit
        # '-v'                : ['-v'],  # print version info and exit
        "-capabilities": ["-capabilities"],  # print compiled-in options and exit
        "-license": ["-license"],  # print license and exit
        "-param": ["-param", "<param_options>"],
        # [device [level [<inst|mod>]]] print a terse summary of model and/or device parameters
        "-doc": ["-doc", "<param_options>"],
        # [device [level [<inst|mod>]]] output latex tables of model and device parameters to files
        "-doc_cat": ["-doc_cat", "<param_options>"],
        # [device [level [<inst|mod>]]] output latex tables of model and device parameters to files
        "-count": ["-count"],  # device count without netlist syntax or topology check
        "-syntax": ["-syntax"],  # check netlist syntax and exit
        "-norun": ["-norun"],  # netlist syntax and topology and exit
        "-namesfile": [
            "-namesfile",
            "<path>",
        ],  # output internal names file to <path> and exit
        "-noise_names_file": [
            "-noise_names_file",
            "<path>",
        ],  # output noise source names file to <path> and exit
        "-quiet": [
            "-quiet"
        ],  # suppress some of the simulation-progress messages sent to stdout
        "-jacobian_test": ["-jacobian_test"],  # jacobian matrix diagnostic
        "-hspice-ext": ["-hspice-ext", "<hsext_options>"],
        # Apply HSPICE compatibility features during parsing. Use option=all to
        # enable every compatibility mode.
        "-redefined_params": ["-redefined_params", "<redef_param_option>"],
        # Configure handling of redefined .param entries: ignore (use last),
        # usefirst, warn, or error.
        "-subckt_multiplier": ["-subckt_multiplier", "<truefalse_option>"],
        # Set option to true (default) or false to apply implicit subcircuit multipliers.
        "-delim": [
            "-delim",
            "<delim_option>",
        ],  # Set the output file field delimiter (<TAB|COMMA|string>).
        "-o": ["-o", "<basename>"],  # Base name for the output files.
        # '-l': ['-l', '<path>'],  # Log output to <path> or "cout".
        "-per-processor": [
            "-per-processor"
        ],  # Create log files for each processor; append .<n>.<r> to the path.
        "-remeasure": ["-remeasure", "<path>"],
        # Recompute .measure() results using an existing Xyce output file.
        "-nox": [
            "-nox",
            "onoff_option",
        ],  # <on|off>               NOX nonlinear solver usage
        "-linsolv": [
            "-linsolv",
            "<solver>",
        ],  # <solver>           force usage of specific linear solver
        "-maxord": [
            "-maxord",
            "<int_option>",
        ],  # <1..5>              maximum time integration order
        "-max-warnings": [
            "-max-warnings",
            "<int_option>",
        ],  # <#>           maximum number of warning messages
        "-prf": [
            "-prf",
            "<path>",
        ],  # <param file name>      specify a file with simulation parameters
        "-rsf": [
            "-rsf",
            "<path>",
        ],  # Specify a file to save simulation response functions.
        # '-r': ['-r', '<path>'],  # Generate a raw file in binary format.
        "-a": ["-a"],  # Combine with -r <file> to output in ASCII format.
        "-randseed": ["-randseed", "<int_option>"],
        # Seed the random number generator used by expressions and sampling methods.
        "-plugin": [
            "-plugin",
            "<plugin_list>",
        ],  # load device plugin libraries (comma-separated list)
    }
    """:meta private:"""

    _default_run_switches: ClassVar[list[str]] = ["-l", "-r"]

    @classmethod
    def valid_switch(
        cls, switch: str, switch_param: str | Sequence[str] | None = None
    ) -> list[str]:
        """Validates a command line switch. The following options are available for
        Xyce:

        * `-capabilities`: print compiled-in options and exit * `-license`: print
        license and exit * `-param [device [level [<inst|mod>]]]`: print a terse summary
        of model and/or device parameters * `-doc [device [level [<inst|mod>]]]`: output
        latex tables of model and device parameters to files * `-doc_cat [device [level
        [<inst|mod>]]]`: output latex tables of model and device parameters to files *
        `-count`: device count without netlist syntax or topology check * `-syntax`:
        check netlist syntax and exit * `-norun`: netlist syntax and topology and exit *
        `-namesfile <path>`: output internal names file to <path> and exit *
        `-noise_names_file <path>`: output noise source names file to <path> and exit *
        `-quiet`: suppress some of the simulation-progress messages sent to stdout *
        `-jacobian_test`: jacobian matrix diagnostic * `-hspice-ext  <option>`: apply
        hspice compatibility features during parsing.  option=all applies them all *
        `-redefined_params <option>`: set option for redefined .params as ignore (use
        last), usefirst, warn or error * `-subckt_multiplier <option>`: set option to
        true(default) or false to apply implicit subcircuit multipliers *
        `-local_variation <option>`: set option to true(default) or false to enable
        local variation in UQ analysis * `-delim <TAB|COMMA|string>`: set the output
        file field delimiter * `-o <basename>`: <basename> for the output file(s) *
        `-per-processor`: create log file for each procesor, add .<n>.<r> to log path *
        `-remeasure [existing Xyce output file]`: recompute .measure() results with
        existing data * `-nox <on|off>`: NOX nonlinear solver usage * `-linsolv
        <solver>`: force usage of specific linear solver * `-maxord <1..5>`: maximum
        time integration order * `-max-warnings <#>`: maximum number of warning messages
        * `-prf <param file name>`: specify a file with simulation parameters * `-rsf
        <response file name>`: specify a file to save simulation responses functions. *
        `-a`: output in ascii format * `-randseed <number>`: seed random number
        generator used by expressions and sampling methods * `-plugin <plugin list>`:
        load device plugin libraries (comma-separated list)

        The following parameters will already be filled in by kupicelib, and cannot be
        set:

        * `-l <path>`: place the log output into <path>, "cout" to log to stdout * `-r
        <file>`: generate a rawfile named <file> in binary format

        :param switch: switch to be added.
        :type switch: str
        :param parameter: parameter for the switch
        :type parameter: str, optional
        :return: the correct formatting for the switch
        :rtype: list
        """
        ret: list[str] = []
        if isinstance(switch_param, str):
            parameter_text = switch_param.strip()
        elif isinstance(switch_param, Sequence):
            parameter_text = " ".join(str(part) for part in switch_param).strip()
        elif switch_param is None:
            parameter_text = ""
        else:
            parameter_text = str(switch_param).strip()

        switch_clean = switch.strip()
        if not switch_clean:
            return ret
        if not switch_clean.startswith("-"):
            switch_clean = "-" + switch_clean

        if switch_clean in cls._default_run_switches:
            _logger.info(
                "Switch %s is already in the default switches",
                switch_clean,
            )
            return []

        if switch_clean in cls.xyce_args:
            switch_list = cls.xyce_args[switch_clean]
            if len(switch_list) == 2:
                param_token = switch_list[1]
                if param_token == "<path>":
                    ret = [switch_list[0], parameter_text]
                elif param_token == "<param_options>":
                    # Check for [device [level [<inst|mod>]]] syntax ??
                    # TODO: this will probably not work, need to separate the parameters
                    ret = [switch_list[0], parameter_text]
                elif param_token == "<hsext_options>":
                    ret = [switch_list[0], parameter_text]
                elif param_token == "<redef_param_option>":
                    if parameter_text in ("ignore", "uselast", "usefirst", "warn", "error"):
                        ret = [switch_list[0], parameter_text]
                elif param_token == "<truefalse_option>":
                    if parameter_text.lower() in ("true", "false"):
                        ret = [switch_list[0], parameter_text]
                elif param_token == "<delim_option>":
                    ret = [switch_list[0], parameter_text]
                elif param_token == "<onoff_option>":
                    if parameter_text.lower() in ("on", "off"):
                        ret = [switch_list[0], parameter_text]
                elif param_token == "<int_option>":
                    try:
                        int(parameter_text)
                    except ValueError:
                        pass
                    else:
                        ret = [switch_list[0], parameter_text]
                elif param_token == "<plugin_list>":
                    ret = [switch_list[0], parameter_text]
                else:
                    _logger.warning(
                        "Invalid parameter %s for switch '%s'",
                        parameter_text,
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
        """Executes a Xyce simulation run.

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
            _logger.error("Unable to find the Xyce executable.")
            _logger.error("A specific location of the Xyce can be set")
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
        rawfile = netlist_path.with_suffix(".raw").as_posix()

        cmd_run = (
            cls.spice_exe
            + switches_list
            + ["-l"]
            + [logfile]
            + ["-r"]
            + [rawfile]
            + [netlist_path.as_posix()]
        )
        # start execution
        if exe_log:
            log_exe_file = netlist_path.with_suffix(".exe.log")
            with open(log_exe_file, "w", encoding="utf-8") as outfile:
                error = run_function(
                    cmd_run, timeout=timeout, stdout=outfile, stderr=subprocess.STDOUT
                )
        else:
            error = run_function(cmd_run, timeout=timeout, stdout=stdout, stderr=stderr)
        return error
