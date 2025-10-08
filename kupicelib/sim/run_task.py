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
# Name:        run_task.py
# Purpose:     Class used for a spice tool using a process call
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     23-12-2016
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
"""Internal classes not to be used directly by the user."""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from time import sleep
from typing import Any

from .process_callback import ProcessCallback
from .simulator import Simulator

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2023, Fribourg Switzerland"

_logger = logging.getLogger("kupicelib.RunTask")

# Configure structured logging formatter if python-json-logger is installed
try:
    from pythonjsonlogger import jsonlogger  # type: ignore[attr-defined]

    handler = logging.StreamHandler()
    json_formatter = jsonlogger.JsonFormatter(  # type: ignore[attr-defined]
        '%(asctime)s %(name)s %(levelname)s '
        '[runno=%(runno)s netlist=%(netlist)s] %(message)s'
    )
    handler.setFormatter(json_formatter)
    if not _logger.handlers:
        _logger.addHandler(handler)
except ImportError:
    pass

END_LINE_TERM = "\n"

if sys.version_info.major >= 3 and sys.version_info.minor >= 6:
    clock_function = time.time
else:
    clock_function = time.perf_counter


def format_time_difference(time_diff: float) -> str:
    """Formats the time difference in a human-readable format, stripping the hours or
    minutes if they are zero."""
    seconds_difference = int(time_diff)
    milliseconds = int((time_diff - seconds_difference) * 1000)
    hours, remainder = divmod(seconds_difference, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours == 0:
        if minutes == 0:
            return f"{int(seconds):02d}.{milliseconds:04d} secs"
        else:
            return f"{int(minutes):02d}:{int(seconds):02d}.{milliseconds:04d}"
    else:
        return (
            f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}.{milliseconds:04d}"
        )


class RunTask:
    """This is an internal Class and should not be used directly by the User."""

    def __init__(
        self,
        simulator: type[Simulator],
        runno: int,
        netlist_file: Path,
        callback: type[ProcessCallback] | Callable[..., object] | None,
        callback_args: Mapping[str, Any] | None = None,
        switches: Sequence[str] | None = None,
        timeout: float | None = None,
        verbose: bool = False,
        exe_log: bool = False,
    ) -> None:
        self.start_time: float | None = None
        self.stop_time: float | None = None
        self.verbose = verbose
        self.switches: list[str] | None = list(switches) if switches is not None else None
        self.timeout = timeout  # Thanks to Daniel Phili for implementing this
        self.simulator: type[Simulator] = simulator
        self.runno: int = runno
        self.netlist_file: Path = netlist_file
        self.callback: type[ProcessCallback] | Callable[..., object] | None = (
            callback
        )
        self.callback_args: dict[str, Any] | None = (
            dict(callback_args) if callback_args is not None else None
        )
        self.retcode: int = -1  # Signals an error by default
        self.raw_file: Path | None = None
        self.log_file: Path | None = None
        self.callback_return: object | None = None
        self.exe_log = exe_log
        # Create a LoggerAdapter to include run number and netlist in logs
        self.logger: logging.LoggerAdapter[logging.Logger] = logging.LoggerAdapter(
            _logger, {"runno": self.runno, "netlist": str(self.netlist_file)}
        )

    def print_info(self, logger_fun: Callable[[str], object], message: str) -> None:
        # Use contextual logger for info/error messages
        logger_fun(message)
        if self.verbose:
            print(f"{time.asctime()} {logger_fun.__name__}: {message}{END_LINE_TERM}")

    def run(self) -> None:
        # Running the Simulation

        self.start_time = clock_function()
        self.print_info(
            _logger.info,
            f": Starting simulation {self.runno}: {self.netlist_file}",
        )
        # Ensure simulator executable is configured if missing
        simulator_cls: type[Simulator] = self.simulator
        if not simulator_cls.spice_exe and hasattr(
            simulator_cls, "get_default_executable"
        ):
            simulator_cls = simulator_cls.create_from(path_to_exe=None)
            self.simulator = simulator_cls
        # start execution
        run_result = simulator_cls.run(
            self.netlist_file.absolute().as_posix(),
            cmd_line_switches=self.switches,
            timeout=self.timeout,
            exe_log=self.exe_log,
        )
        self.retcode = int(run_result)
        self.stop_time = clock_function()
        # print simulation time with format HH:MM:SS.mmmmmm

        # Calculate the time difference
        sim_time = format_time_difference(self.stop_time - self.start_time)
        # Format the time difference
        log_file = self.netlist_file.with_suffix(".log")
        self.log_file = log_file

        # Cleanup everything
        if self.retcode == 0:
            raw_file = self.netlist_file.with_suffix(self.simulator.raw_extension)
            self.raw_file = raw_file
            if raw_file.exists() and log_file.exists():
                # simulation successful
                self.print_info(
                    _logger.info, f"Simulation Successful. Time elapsed: {sim_time}"
                )

                if self.callback:
                    if self.callback_args is not None:
                        callback_print = ", ".join(
                            [
                                f"{key}={value}"
                                for key, value in self.callback_args.items()
                            ]
                        )
                    else:
                        callback_print = ""
                    message = (
                        f"Simulation finished. Calling {self.callback.__name__}"
                        f"(rawfile, logfile{callback_print})."
                    )
                    self.print_info(_logger.info, message)
                    try:
                        if self.callback_args is not None:
                            return_or_process = self.callback(
                                raw_file, log_file, **self.callback_args
                            )
                        else:
                            return_or_process = self.callback(raw_file, log_file)
                    except Exception:
                        # Log exception with full traceback
                        self.logger.exception("Exception during callback execution")
                    else:
                        if isinstance(return_or_process, ProcessCallback):
                            proc = return_or_process
                            proc.start()
                            self.callback_return = proc.queue.get()
                            proc.join()
                        else:
                            self.callback_return = return_or_process
                    finally:
                        callback_start_time = self.stop_time
                        self.stop_time = clock_function()
                        self.print_info(
                            _logger.info,
                            "Callback Finished. Time elapsed: {}".format(format_time_difference(
                                self.stop_time - callback_start_time
                            )),
                        )
                else:
                    self.print_info(
                        _logger.info, "Simulation Finished. No Callback function given"
                    )
            else:
                self.print_info(
                    _logger.error, "Simulation Raw file or Log file were not found"
                )
        else:
            # Simulation failed
            self.logger.error("Simulation Aborted. Time elapsed: %s", sim_time)
            if log_file.exists():
                self.log_file = log_file.replace(log_file.with_suffix(".fail"))

    def get_results(self) -> object | tuple[Path | None, Path | None] | None:
        """Returns the simulation outputs if the simulation and callback function has
        already finished.

        If the simulation is not finished, it simply returns None. If no callback
        function is defined, then it returns a tuple with (raw_file, log_file). If a
        callback function is defined, it returns whatever the callback function is
        returning.
        """
        # simulation not started or still running if retcode unset
        if self.retcode == -1:
            return None

        if self.retcode == 0:  # All finished OK
            if self.callback:
                return self.callback_return
            else:
                return self.raw_file, self.log_file
        else:
            if self.callback:
                return None
            else:
                return self.raw_file, self.log_file

    def wait_results(self) -> object | tuple[Path | None, Path | None]:
        """Waits for the completion of the task and returns a tuple with the raw and log
        files.

        :returns: Tuple with the path to the raw file and the path to the log file
        :rtype: tuple(str, str)
        """
        # wait until simulation run() has been executed
        while self.retcode == -1:
            sleep(0.1)
        return self.get_results()

    def __call__(self) -> RunTask:
        """Allow this object to be submitted to an Executor."""
        self.run()
        return self
