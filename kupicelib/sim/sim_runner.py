#!/usr/bin/env python
# coding=utf-8
# flake8: noqa: E501

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        sim_runner.py
# Purpose:     Tool used to launch LTSpice simulation in batch mode.
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     23-12-2016
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
"""Allows launching LTSpice simulations from a Python Script, thus allowing to overcome
the 3 dimensions STEP limitation on LTSpice, update resistor values, or component
models.

The code snipped below will simulate a circuit with two different diode models, set the
simulation temperature to 80 degrees, and update the values of R1 and R2 to 3.3k. ::

from kupicelib.sim.sim_runner import SimRunner from kupicelib.sim.sweep import sweep
from kupicelib.editor.spice_editor import SpiceEditor from
kupicelib.sim.ltspice_simulator import LTspice

runner = SimRunner(simulator=LTspice, parallel_sims=4) editor =
SpiceEditor("my_circuit.net") editor.set_parameters(temp=80)  # Sets the simulation
temperature to be 80 degrees editor.set_component_value('R2', '3.3k')  #  Updates the
resistor R2 value to be 3.3k for dmodel in ("BAT54", "BAT46WJ"):
editor.set_element_model("D1", model)  # Sets the Diode D1 model     for res_value in
sweep(2.2, 2,4, 0.2):  # Steps from 2.2 to 2.4 with 0.2 increments
editor.set_component_value('R1', res_value)  #  Updates the resistor R1 value to be 3.3k
runner.run()

runner.wait_completion()  # Waits for the LTSpice simulations to complete

print("Total Simulations: {}".format(runner.runno)) print("Successful Simulations:
{}".format(runner.okSim)) print("Failed Simulations: {}".format(runner.failSim))

The first line will create a python class instance that represents the LTSpice file or
netlist that is to be simulated. This object implements methods that are used to
manipulate the spice netlist. For example, the method set_parameters() will set or
update existing parameters defined in the netlist. The method set_component_value() is
used to update existing component values or models.

--------------- Multiprocessing ---------------

For making better use of today's computer capabilities, the SimRunner spawns several
simulation processes each executing in parallel a simulation.

By default, the number of parallel simulations is 4, however the user can override this
in two ways. Either using the class constructor argument ``parallel_sims`` or by forcing
the allocation of more processes in the run() call by setting ``wait_resource=False``.
::

`runner.run(wait_resource=False)`

The recommended way is to set the parameter ``parallel_sims`` in the class constructor.
::

`runner = SimRunner(simulator=LTspice, parallel_sims=8)`

The user then can launch a simulation with the updates done to the netlist by calling
the run() method. Since the processes are not executed right away, but rather just
scheduled for simulation, the wait_completion() function is needed if the user wants to
execute code only after the completion of all scheduled simulations.

The usage of wait_completion() is optional. Just note that the script will only end when
all the scheduled tasks are executed.

--------- Callbacks ---------

As seen above, the `wait_completion()` can be used to wait for all the simulations to be
finished. However, this is not efficient from a multiprocessor point of view. Ideally,
the post-processing should be also handled while other simulations are still running.
For this purpose, the user can use a function call back.

The callback function is called when the simulation has finished directly by the thread
that has handling the simulation. A function callback receives two arguments. The RAW
file and the LOG file names. Below is an example of a callback function::

def processing_data(raw_filename, log_filename):     '''This is a call back function
that just prints the filenames'''     print("Simulation Raw file is %s. The log is %s" %
(raw_filename, log_filename)     # Other code below either using ltsteps.py or
raw_read.py     log_info = LTSpiceLogReader(log_filename)     log_info.read_measures()
rise, measures = log_info.dataset["rise_time"]

The callback function is optional. If  no callback function is given, the thread is
terminated just after the simulation is finished.
"""
__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2020, Fribourg Switzerland"

__all__ = [
    "SimRunner",
    "SimRunnerTimeoutError",
    "SimRunnerConfigError",
    "AnyRunner",
    "ProcessCallback",
    "RunTask",
    "clock_function",
]

import concurrent.futures
import inspect  # Library used to get the arguments of the callback function
import logging
import shutil
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from time import sleep
from time import thread_time as clock
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Protocol,
    Tuple,
    Type,
    Union,
    cast,
)

from ..editor.base_editor import BaseEditor
from ..sim.run_task import RunTask, clock_function
from ..sim.simulator import Simulator
from .process_callback import ProcessCallback

_logger = logging.getLogger("kupicelib.SimRunner")
END_LINE_TERM = "\n"

# Define a callback type alias for readability
CallbackType = Union[
    Type[ProcessCallback],
    Callable[[Path, Path], Any],
]


class SimRunnerTimeoutError(TimeoutError):
    """Timeout Error class."""


class SimRunnerConfigError(Exception):
    """Configuration error for SimRunner."""


class AnyRunner(Protocol):
    def run(
        self,
        netlist: Union[str, Path, BaseEditor],
        *,
        wait_resource: bool = True,
        callback: Optional[Union[Type[ProcessCallback], Callable]] = None,
        callback_args: Optional[Union[tuple, dict]] = None,
        switches: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        run_filename: Optional[str] = None,
        exe_log: bool = False,
    ) -> Optional[RunTask]: ...

    def wait_completion(self, timeout=None, abort_all_on_timeout=False) -> bool: ...


class SimRunner(AnyRunner):
    """The SimRunner class implements all the methods required for launching batches of
    Spice simulations.

    :raises FileNotFoundError: When the file is not found /!\\ This will be changed
    :param parallel_sims: Defines the number of parallel simulations that can be
        executed at the same time. Ideally this number should be aligned to the number
        of CPUs (processor cores) available on the machine.
    :type parallel_sims: int, optional
    :param timeout: Timeout parameter as specified on the os subprocess.run() function.
        Default is 600 seconds, i.e. 10 minutes. For no timeout, set to None.
    :type timeout: float, optional
    :param verbose: If True, it enables a richer printout of the program execution.
    :type verbose: bool, optional
    :param output_folder: specifying which directory shall be used for simulation files
        (raw and log files).
    :type output_folder: str, optional
    :param simulator: Forcing a given simulator executable.
    :type simulator: Simulator, optional
    """

    def __init__(
        self,
        *,
        simulator=None,
        parallel_sims: int = 4,
        timeout: float = 600.0,
        verbose: bool = False,
        output_folder: Optional[str] = None,
    ):
        # The '*' in the parameter list forces the user to use named parameters for the
        # rest of the parameters.
        # This is a good practice to avoid confusion.
        self.verbose = verbose
        self.timeout = timeout
        self.cmdline_switches: List[str] = []

        # Define output_folder attribute with type annotation once
        self.output_folder: Optional[Path] = None
        if output_folder:
            self.output_folder = Path(
                output_folder
            )  # If not None converts to Path() object
            if not self.output_folder.exists():
                self.output_folder.mkdir()

        self.parallel_sims = parallel_sims
        # Executor for parallel simulations
        self._executor: ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.parallel_sims
        )
        # track pairs of (task, future)
        self.active_tasks: List[Tuple[RunTask, Future]] = []
        self.completed_tasks: List[RunTask] = []
        self._iterator_counter = 0  # Note: Nested iterators are not supported

        self.run_count: int = 0  # number of total runs
        self.failed_simulations: int = 0  # number of failed simulations
        self.successful_simulations: int = 0  # number of successful completed simulations
        # self.failParam = []  # collects for later user investigation of failed
        # parameter sets

        # Gets a simulator.
        if simulator is None:
            raise SimRunnerConfigError(
                "No default simulator defined; please specify a simulator")
        elif issubclass(simulator, Simulator):
            self.simulator = simulator
        else:
            raise SimRunnerConfigError(
                "Invalid simulator type; expected subclass of Simulator")
        _logger.info("SimRunner initialized")
        if self.verbose:
            _logger.setLevel(logging.DEBUG)
            _logger.debug("Verbose mode enabled: logger level set to DEBUG")
            # also set RunTask logger level to DEBUG
            logging.getLogger("kupicelib.RunTask").setLevel(logging.DEBUG)
            logging.getLogger("kupicelib.RunTask").debug(
                "RunTask logger level set to DEBUG")

    def __del__(self):
        """Class Destructor : Closes Everything."""
        # Wait for all pending simulations to finish
        self.wait_completion(abort_all_on_timeout=True)
        # Shutdown executor, cancelling any pending tasks
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            # older Python versions may not support cancel_futures
            self._executor.shutdown(wait=False)

    def set_simulator(self, spice_tool: Type[Simulator]) -> None:
        """Manually overriding the simulator to be used.

        :param spice_tool: String containing the path to the spice tool to be used, or
            alternatively the Simulator object.
        :type spice_tool: Simulator type
        :return: Nothing
        """
        if issubclass(spice_tool, Simulator):
            self.simulator = spice_tool
        else:
            raise TypeError("Expecting str or Simulator objects")

    def clear_command_line_switches(self) -> None:
        """Clear all the command line switches added previously."""
        self.cmdline_switches.clear()

    def add_command_line_switch(self, switch: str, path: str = "") -> None:
        """Used to add an extra command line argument such as -I<path> to add symbol
        search path or -FastAccess to convert the raw file into Fast Access. The
        argument is a string as is defined in the LTSpice command line documentation.

        :param switch: switch to be added.
        :type switch: str: A command line switch such as "-ascii" for generating a raw
            file in text format or "-alt" for setting the solver to alternate. See
            Command Line Switches information on LTSpice help file.
        :param path: path to the file related to the switch being given.
        :type path: str, optional
        :returns: Nothing
        """
        self.cmdline_switches.append(switch)
        if path is not None:
            self.cmdline_switches.append(path)

    def _on_output_folder(self, afile: Union[str, Path]) -> Path:
        if self.output_folder:
            return self.output_folder / Path(afile).name
        else:
            return Path(afile)

    def _to_output_folder(self, afile: Path, *, copy: bool, new_name: str = "") -> Path:
        if self.output_folder:
            if new_name:
                ddst = self.output_folder / new_name
            else:
                ddst = self.output_folder

            if copy:
                dest = shutil.copy(afile, ddst)
            else:
                dest = shutil.move(afile, ddst)
            return Path(dest)
        else:
            if new_name:
                dest = shutil.copy(afile, afile.parent / new_name)
                return Path(dest)
            else:
                return afile

    def _run_file_name(self, netlist: Union[str, Path]) -> str:
        if not isinstance(netlist, Path):
            netlist = Path(netlist)
        if netlist.suffix == ".qsch":
            # The Qsch files can't be simulated, so, they have to be converted to
            # netlist first.
            netlist = netlist.with_suffix(".net")
        return f"{netlist.stem}_{self.run_count}{netlist.suffix}"

    def _prepare_sim(
        self, netlist: Union[str, Path, BaseEditor], run_filename: Optional[str]
    ) -> Path:
        """Internal function."""
        # update number of simulation
        self.run_count += 1  # Incrementing internal simulation number
        # Harmonize the netlist into a Path object pointing to a netlist file on
        # the right output folder
        if isinstance(netlist, BaseEditor):
            if run_filename is None:
                run_filename = self._run_file_name(netlist.circuit_file)

            # Calculates the path where to store the new netlist.
            run_netlist_file = self._on_output_folder(run_filename)
            netlist.save_netlist(run_netlist_file)

        elif isinstance(netlist, (Path, str)):
            if run_filename is None:
                run_filename = self._run_file_name(netlist)
            if isinstance(netlist, str):
                netlist = Path(netlist)
            run_netlist_file = self._to_output_folder(
                netlist, copy=True, new_name=run_filename
            )
        else:
            raise TypeError(
                "'netlist' parameter must be a SpiceEditor, pathlib.Path, or a str"
            )

        return run_netlist_file

    @staticmethod
    def validate_callback_args(
        callback: Optional[Union[Type[ProcessCallback], Callable]],
        callback_args: Optional[Union[tuple, dict]],
    ) -> Optional[Dict[str, Any]]:
        """It validates that the callback_args are matching the callback function.

        Note that the first two parameters of the callback functions need to be the raw
        and log files.
        """
        if callback is None:
            return None  # No callback function, hence callback_args have no effect
        if inspect.isclass(callback) and issubclass(callback, ProcessCallback):
            args = inspect.signature(callback.callback).parameters
        else:
            args = inspect.signature(callback).parameters
        if len(args) < 2:
            raise ValueError("Callback function must have at least two arguments")
        if len(args) > 2:
            if callback_args is None:
                raise ValueError(
                    "Callback has more than two arguments; callback_args is None"
                )
            if isinstance(callback_args, dict):
                for pos, param in enumerate(args):
                    if pos > 1:
                        if param not in callback_args:
                            raise ValueError(
                                "Callback argument '%s' not found in callback_args"
                                % param
                            )

            if len(args) - 2 != len(callback_args):
                raise ValueError(
                    "Callback function has %d arguments, but %d callback_args are given"
                    % (len(args), len(callback_args))
                )
            if isinstance(callback_args, tuple):
                # Convert into a dictionary
                return {
                    param: callback_args[pos - 2]
                    for pos, param in enumerate(args)
                    if pos > 1
                }
            else:
                return callback_args
        return {}  # Return empty dict for functions with exactly 2 arguments

    def _wait_for_resources(self, wait_resource: bool, timeout: float) -> bool:
        """Internal: blocks until a slot is free or timeout expires."""
        t0 = clock()
        while clock() - t0 < timeout + 1:
            if not wait_resource or (self.active_threads() < self.parallel_sims):
                return True
            sleep(0.1)
        _logger.error(f"Timeout waiting for resources for simulation {self.run_count}")
        return False

    def run(
        self,
        netlist: Union[str, Path, BaseEditor],
        *,
        wait_resource: bool = True,
        callback: Optional[CallbackType] = None,
        callback_args: Optional[Union[tuple, dict]] = None,
        switches: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        run_filename: Optional[str] = None,
        exe_log: bool = False,
    ) -> Optional[RunTask]:
        """Executes a simulation run with the conditions set by the user. Conditions are
        set by the set_parameter, set_component_value or add_instruction functions.

        :param netlist: The name of the netlist can be optionally overridden if the user
            wants to have a better control of how the simulations files are generated.
        :type netlist: SpiceEditor or a path to the file
        :param wait_resource: Setting this parameter to False will force the simulation
            to start immediately, irrespective of the number of simulations already
            active. By default, the SimRunner class uses only four processors. This
            number can be overridden by setting the parameter `parallel_sims` to a
            different number. If there are more than `parallel_sims` simulations being
            done, the new one will be placed on hold till one of the other simulations
            are finished.
        :type wait_resource: bool, optional
        :param callback: The user can optionally give a callback function for when the
            simulation finishes so that processing can be done immediately. The callback
            can either be a function or a class derived from ProcessCallback. A callback
            function must receive two at least input parameters that correspond the raw
            and log files created by the simulation. These need to be the first two
            parameters of the callback function. The other parameters are passed as a
            dictionary or a tuple in the callback_args parameter. If the callback is a
            class derived from ProcessCallback, then the callback is executed in a
            separate process. The callback function must be defined in the callback()
            method of the class. As for the callback function, the first two parameters
            are the raw and log files. The other parameters are passed as dictionary in
            the callback_args parameter.
        :type: callback: function(raw_file: Path, log_file: Path, ...), optional
        :param callback_args: The callback function arguments. This parameter is passed
            as keyword arguments to the callback function.
        :type callback_args: dict or tuple, optional
        :param switches: Command line switches override
        :type switches: list
        :param timeout: Timeout to be used in waiting for resources. Default time is
            value defined in this class constructor.
        :type timeout: float, optional
        :param run_filename: Name to be used for the log and raw file.
        :type run_filename: str or Path
        :param exe_log: If True, the simulator's execution console messages will be
            written to a log file (named ...exe.log) instead of console. This is
            especially useful when running under wine or when running simultaneous
            tasks.
        :type exe_log: bool, optional
        :returns: The task object of type RunTask
        """
        _logger.debug(
            "run called: netlist=%s, wait_resource=%s, switches=%s,"
            " timeout=%s, run_filename=%s, exe_log=%s",
            netlist, wait_resource, switches, timeout, run_filename, exe_log,
        )
        callback_kwargs = self.validate_callback_args(callback, callback_args)
        if switches is None:
            switches = []
        run_netlist_file = self._prepare_sim(netlist, run_filename)

        if timeout is None:
            timeout = self.timeout

        # Wait for an available resource slot or timeout
        if not self._wait_for_resources(wait_resource, timeout):
            if self.verbose:
                _logger.warning(f"Timeout on launching simulation {self.run_count}.")
            return None

        # Prepare command-line switches
        cmdline_switches = switches or self.cmdline_switches

        # Use a dummy callback if None is provided, as RunTask expects a non-None
        # callback
        actual_callback = callback if callback is not None else (lambda raw, log: None)

        # Launch the simulation task via ThreadPoolExecutor
        t = RunTask(
            simulator=self.simulator,
            runno=self.run_count,
            netlist_file=run_netlist_file,
            callback=actual_callback,
            callback_args=callback_kwargs,
            switches=cmdline_switches,
            timeout=timeout,
            verbose=self.verbose,
            exe_log=exe_log,
        )
        future = self._executor.submit(t)
        self.active_tasks.append((t, future))
        _logger.debug(
            "RunTask submitted: runno=%d, netlist_file=%s",
            t.runno,
            t.netlist_file,
        )
        return t

    def run_now(
        self,
        netlist: Union[str, Path, BaseEditor],
        *,
        switches: Optional[List[str]] = None,
        run_filename: Optional[str] = None,
        timeout: Optional[float] = None,
        exe_log: bool = False,
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """Executes a simulation run with the conditions set by the user. Conditions are
        set by the set_parameter, set_component_value or add_instruction functions.

        :param netlist: The name of the netlist can be optionally overridden if the user
            wants to have a better control of how the simulations files are generated.
        :type netlist: SpiceEditor or a path to the file
        :param switches: Command line switches override
        :type switches: list
        :param run_filename: Name to be used for the log and raw file.
        :type run_filename: str or Path
        :param timeout: Timeout to be used in waiting for resources. Default time is
            value defined in this class constructor.
        :type timeout: float, optional
        :param exe_log: If True, the simulator's execution console messages will be
            written to a log file (named ...exe.log) instead of console. This is
            especially useful when running under wine or when running simultaneous
            tasks.
        :type exe_log: bool, optional
        :returns: the raw and log filenames
        """
        if switches is None:
            switches = []
        _logger.debug(
            "run_now called: netlist=%s, switches=%s,"
            " run_filename=%s, timeout=%s, exe_log=%s",
            netlist, switches, run_filename, timeout, exe_log,
        )
        run_netlist_file = self._prepare_sim(netlist, run_filename)

        cmdline_switches = (
            switches or self.cmdline_switches
        )  # If switches are passed, they override the ones inside
        # the class.

        if timeout is None:
            timeout = self.timeout

        def dummy_callback(raw, log):
            """Dummy call back that does nothing."""
            return None

        t = RunTask(
            simulator=self.simulator,
            runno=self.run_count,
            netlist_file=run_netlist_file,
            callback=dummy_callback,
            callback_args=None,
            switches=cmdline_switches,
            timeout=timeout,
            verbose=self.verbose,
            exe_log=exe_log,
        )
        # Run synchronously
        t()
        _logger.debug(
            "RunTask (run_now) completed: retcode=%d, raw_file=%s, log_file=%s",
            t.retcode, t.raw_file, t.log_file,
        )
        self.completed_tasks.append(t)
        if t.retcode == 0:
            self.successful_simulations += 1
        else:
            # simulation failed
            self.failed_simulations += 1
        return t.raw_file, t.log_file  # Returns the raw and log file

    def active_threads(self) -> int:
        """Returns the number of active sim_tasks."""
        self.update_completed()
        return len(self.active_tasks)

    def update_completed(self) -> None:
        """This function updates the active_tasks and completed_tasks lists. It moves
        the finished task from the active_tasks list to the completed_tasks list. It
        should be called periodically to update the status of the simulations.

        :returns: Nothing
        """
        _logger.debug(
            "update_completed: active=%d, completed=%d", len(
                self.active_tasks), len(
                self.completed_tasks))
        i = 0
        while i < len(self.active_tasks):
            task, future = self.active_tasks[i]
            if not future.done():
                i += 1
            else:
                if task.retcode == 0:
                    self.successful_simulations += 1
                else:
                    self.failed_simulations += 1
                self.active_tasks.pop(i)
                self.completed_tasks.append(task)
                _logger.debug(
                    "Task %d moved from active to completed (retcode=%d)",
                    task.runno,
                    task.retcode,
                )

    def kill_all_ltspice(self) -> None:
        """.. deprecated:: 1.0 Use `kill_all_spice()` instead.

        This is only here for compatibility with previous code.

        Function to terminate LTSpice
        """
        self.kill_all_spice()

    def kill_all_spice(self) -> None:
        """Function to terminate xxSpice processes."""
        simulator = Simulator
        process_name = simulator.process_name
        try:
            import psutil
        except ImportError:
            _logger.error("psutil library not installed, cannot kill processes")
            return

        for proc in psutil.process_iter():
            # check whether the process name matches
            if proc.name() == process_name:
                _logger.info(f"killing Spice {proc.pid}")
                proc.kill()

    def _maximum_stop_time(self) -> Optional[float]:
        """This function will return the maximum timeout time of all active tasks.

        :return: Maximum timeout time or None, if there is no timeout defined.
        :rtype: float or None
        """
        alarm: Optional[float] = None
        for task, future in self.active_tasks:
            # Determine appropriate timeout value for this task
            timeout_val = task.timeout if task.timeout is not None else self.timeout
            if timeout_val is None:
                continue
            # Cast to float now that timeout_val is guaranteed
            candidate = cast(float, task.start_time) + cast(float, timeout_val)
            if alarm is None or candidate > alarm:
                alarm = candidate
        return alarm

    def wait_completion(
            self,
            timeout: Optional[float] = None,
            abort_all_on_timeout: bool = False) -> bool:
        """This function will wait for the execution of all scheduled simulations to
        complete.

        :param timeout: Cancels the wait after the number of seconds specified by the
            timeout. This timeout is reset everytime that a simulation is completed. The
            difference between this timeout and the one defined in the SimRunner
            instance, is that the latter is implemented by the subprocess class, and
            this one just cancels the wait.
        :type timeout: int
        :param abort_all_on_timeout: attempts to stop all LTSpice processes if timeout
            is expired.
        :type abort_all_on_timeout: bool
        :returns: True if all simulations were executed successfully
        :rtype: bool
        """
        _logger.debug(
            "wait_completion called: timeout=%s, abort_all_on_timeout=%s",
            timeout,
            abort_all_on_timeout)
        self.update_completed()
        stop_time: Optional[float] = None
        if timeout is not None:
            stop_time = clock_function() + timeout
        while len(self.active_tasks) > 0:
            sleep(1)
            self.update_completed()
            if timeout is None:
                stop_time = self._maximum_stop_time()
            if (
                stop_time is not None
            ):  # This can happen if timeout was set as none everywhere
                if clock_function() > stop_time:
                    if abort_all_on_timeout:
                        self.kill_all_spice()
                    return False

        _logger.debug("wait_completion returning %s", self.failed_simulations == 0)
        return self.failed_simulations == 0

    @staticmethod
    def _del_file_if_exists(workfile: Optional[Path]):
        """Deletes a file if it exists.

        :param workfile: File to be deleted
        :type workfile: Path
        :return: Nothing
        """
        if workfile is not None and workfile.exists():
            _logger.info("Deleting..." + workfile.name)
            workfile.unlink()

    @staticmethod
    def _del_file_ext_if_exists(workfile: Path, ext: str):
        """Deletes a file extension if it exists.

        :param workfile: File to be deleted
        :type workfile: Path
        :param ext: Extension to be deleted
        :type ext: str
        :return: Nothing
        """
        sim_file = workfile.with_suffix(ext)
        SimRunner._del_file_if_exists(sim_file)

    def cleanup_files(self) -> None:
        """Will delete all log and raw files that were created by the script.

        This should only be executed at the end of data processing.
        """
        self.update_completed()  # Updates the active_tasks and completed_tasks lists

        for task in self.completed_tasks:
            netlistfile = task.netlist_file
            self._del_file_if_exists(
                netlistfile
            )  # Delete the netlist file if still exists
            self._del_file_if_exists(
                task.log_file
            )  # Delete the log file if was created
            self._del_file_if_exists(
                netlistfile.with_suffix(".exe.log")
            )  # Delete the log file if was created
            self._del_file_if_exists(
                task.raw_file
            )  # Delete the raw file if was created

            if netlistfile.suffix == ".net" or netlistfile.suffix == ".asc":
                # Delete the files that have been potentially created by LTSpice
                for ext in (".log.raw", ".op.raw"):
                    self._del_file_ext_if_exists(netlistfile, ext)

                if (
                    netlistfile.suffix == ".asc"
                ):  # If simulated from an asc file, delete the .net file
                    # Then needs to delete the .net as well
                    self._del_file_ext_if_exists(netlistfile, ".net")

    def file_cleanup(self) -> None:
        """..

        deprecated:: 1.0 Use `cleanup_files()` instead.
        """
        self.cleanup_files()  # alias for backward compatibility

    def __iter__(self) -> Iterator:
        self._iterator_counter = (
            0  # Reset the iterator counter. Note: nested iterators are not supported
        )
        return self

    def __next__(self) -> Any:
        while True:
            self.update_completed()  # update active and completed tasks
            # First go through the completed tasks
            if self._iterator_counter < len(self.completed_tasks):
                ret = self.completed_tasks[self._iterator_counter]
                self._iterator_counter += 1
                if ret.retcode == 0:
                    return ret.get_results()
                else:
                    _logger.error(f"Skipping {ret.runno} because simulation failed.")

            # Then check if there are any active tasks
            if len(self.active_tasks) == 0:
                raise StopIteration

            # Then go through the active tasks to get the maximum timeout
            stop_time = self._maximum_stop_time()

            if (
                stop_time is not None and clock_function() > stop_time
            ):  # All tasks are on timeout condition
                raise SimRunnerTimeoutError(
                    f"Exceeded {self.timeout} seconds waiting for tasks to finish"
                )

            # Wait for the active tasks to finish with a timeout
            sleep(0.2)  # Go asleep for a while
