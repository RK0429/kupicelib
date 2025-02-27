#!/usr/bin/env python
# coding=utf-8

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        sim_analysis.py
# Purpose:     Classes to automate Monte-Carlo, FMEA or Worst Case Analysis
#              be updated by user instructions
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     06-07-2021
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

import logging
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from ...editor.base_editor import BaseEditor
from ...log.logfile_data import LogfileData
from ...log.ltsteps import LTSpiceLogReader
from ...log.qspice_log_reader import QspiceLogReader
from ...utils.detect_encoding import EncodingDetectError
from ..sim_runner import AnyRunner, ProcessCallback, RunTask

_logger = logging.getLogger("spicelib.SimAnalysis")

# Define a type variable for the editor to handle both BaseEditor and its subclasses
EditorType = TypeVar("EditorType", bound=BaseEditor)

# Type definitions for LogfileData attributes
StepsetDict = Dict[str, List[Any]]
DatasetDict = Dict[str, List[Any]]


class SimAnalysis(object):
    """
    Base class for making Monte-Carlo, Extreme Value Analysis (EVA) or Failure Mode and Effects Analysis.
    As a base class, a certain number of assertions must be made on the simulation results that will make the pass/fail.

    Note: For the time being only measurements done with .MEAS are possible. At a later stage the parsing of RAW files
    will be possible, although, it seems that the later solution is less computing intense.
    """

    def __init__(
        self, circuit_file: Union[str, BaseEditor], runner: Optional[AnyRunner] = None
    ):
        if isinstance(circuit_file, str):
            from ...editor.spice_editor import SpiceEditor

            self.editor: BaseEditor = SpiceEditor(circuit_file)
        else:
            # If it's not a string, it's already a BaseEditor
            self.editor = circuit_file
        self._runner = runner
        self.simulations: List[Optional[RunTask]] = []
        self.last_run_number = 0
        self.received_instructions: List[Tuple[str, ...]] = []
        self.instructions_added = False
        self.log_data = LogfileData()

    def clear_simulation_data(self) -> None:
        """Clears the data from the simulations"""
        self.simulations.clear()

    @property
    def runner(self) -> AnyRunner:
        if self._runner is None:
            from ...sim.sim_runner import SimRunner

            self._runner = SimRunner()
        return self._runner

    @runner.setter
    def runner(self, new_runner: AnyRunner) -> None:
        self._runner = new_runner

    def run(
        self,
        *,
        wait_resource: bool = True,
        callback: Optional[Union[Type[ProcessCallback], Callable[..., Any]]] = None,
        callback_args: Optional[Union[Tuple[Any, ...], Dict[str, Any]]] = None,
        switches: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        run_filename: Optional[str] = None,
        exe_log: bool = True,
    ) -> Optional[RunTask]:
        """
        Runs the simulations. See runner.run() method for details on arguments.

        Note: The exe_log parameter is only used if the runner supports it.
        """
        # AnyRunner interface doesn't include exe_log, so we need to omit it
        # to avoid type errors with strict implementations of AnyRunner
        sim = self.runner.run(
            self.editor,
            wait_resource=wait_resource,
            callback=callback,
            callback_args=callback_args,
            switches=switches,
            timeout=timeout,
            run_filename=run_filename,
        )

        if sim is not None:
            self.simulations.append(sim)
            return sim
        return None

    def wait_completion(self) -> None:
        self.runner.wait_completion()

    @wraps(BaseEditor.reset_netlist)
    def reset_netlist(self) -> None:
        """Resets the netlist to the original state and clears the instructions added by the user."""
        self._reset_netlist()
        self.received_instructions.clear()

    def _reset_netlist(self) -> None:
        """Unlike the reset_netlist method of the BaseEditor, this method does not clear the instructions added by the
        user. This is useful for the case where the user wants to run multiple simulations with different parameters
        without having to add the instructions again."""
        self.editor.reset_netlist()
        self.instructions_added = False

    def set_component_value(self, ref: str, new_value: str) -> None:
        self.received_instructions.append(("set_component_value", ref, new_value))

    def set_element_model(self, ref: str, new_model: str) -> None:
        self.received_instructions.append(("set_element_model", ref, new_model))

    def set_parameter(self, ref: str, new_value: str) -> None:
        self.received_instructions.append(("set_parameter", ref, new_value))

    def add_instruction(self, new_instruction: str) -> None:
        self.received_instructions.append(("add_instruction", new_instruction))

    def remove_instruction(self, instruction: str) -> None:
        self.received_instructions.append(("remove_instruction", instruction))

    def remove_Xinstruction(self, search_pattern: str) -> None:
        self.received_instructions.append(("remove_Xinstruction", search_pattern))

    def play_instructions(self) -> None:
        if self.instructions_added:
            return  # Nothing to do
        for instruction in self.received_instructions:
            if instruction[0] == "set_component_value":
                self.editor.set_component_value(instruction[1], instruction[2])
            elif instruction[0] == "set_element_model":
                self.editor.set_element_model(instruction[1], instruction[2])
            elif instruction[0] == "set_parameter":
                self.editor.set_parameter(instruction[1], instruction[2])
            elif instruction[0] == "add_instruction":
                self.editor.add_instruction(instruction[1])
            elif instruction[0] == "remove_instruction":
                self.editor.remove_instruction(instruction[1])
            elif instruction[0] == "remove_Xinstruction":
                self.editor.remove_Xinstruction(instruction[1])
            else:
                raise ValueError("Unknown instruction")
        self.instructions_added = True

    def save_netlist(self, filename: str) -> None:
        self.play_instructions()
        self.editor.save_netlist(filename)

    def cleanup_files(self) -> None:
        """Clears all simulation files. Typically used after a simulation run and analysis."""
        # Check if runner has cleanup_files method
        if hasattr(self.runner, "cleanup_files"):
            self.runner.cleanup_files()
        else:
            _logger.warning("The runner does not support cleanup_files method")

    def simulation(self, index: int) -> Optional[RunTask]:
        """Returns a simulation object"""
        return self.simulations[index]

    def __getitem__(self, item: int) -> Optional[RunTask]:
        return self.simulations[item]

    @staticmethod
    def read_logfile(run_task: RunTask) -> Optional[LogfileData]:
        """Reads the log file and returns a dictionary with the results"""
        if run_task.simulator.__name__ == "LTspice":
            LogReader = LTSpiceLogReader
        elif run_task.simulator.__name__ == "Qspice":
            # Cast to ensure type safety since we know both classes have similar interfaces
            LogReader = cast(Type[LTSpiceLogReader], QspiceLogReader)
        else:
            raise ValueError("Unknown simulator type")

        try:
            # Ensure log_file is not None before passing to LogReader
            if run_task.log_file is None:
                return None
            log_results = LogReader(run_task.log_file)
        except FileNotFoundError:
            _logger.warning("Log file not found: %s", run_task.log_file)
            return None
        except EncodingDetectError:
            _logger.warning("Log file %s couldn't be read", run_task.log_file)
            return None
        return log_results

    def add_log_data(self, log_data: LogfileData) -> None:
        """Add data from a log file to the log_data object"""
        if log_data is None:
            return

        # Explicitly annotate types for better type checking
        log_stepset: StepsetDict = log_data.stepset  # type: ignore
        log_dataset: DatasetDict = log_data.dataset  # type: ignore
        self_stepset: StepsetDict = self.log_data.stepset  # type: ignore
        self_dataset: DatasetDict = self.log_data.dataset  # type: ignore

        for param in log_stepset:
            if param not in self_stepset:
                self_stepset[param] = log_stepset[param]
            else:
                self_stepset[param].extend(log_stepset[param])
        for param in log_dataset:
            if param not in self_dataset:
                self_dataset[param] = log_dataset[param][:]
            else:
                self_dataset[param].extend(log_dataset[param][:])
        self.log_data.step_count += log_data.step_count

    def read_logfiles(self) -> LogfileData:
        """Reads the log files and returns a dictionary with the results"""
        self.log_data = LogfileData()  # Clears the log data
        for sim in self.simulations:
            if sim is None:
                continue

            log_results = self.read_logfile(sim)
            if log_results is not None:
                self.add_log_data(log_results)

        return self.log_data

    def configure_measurement(
        self, meas_name: str, meas_expression: str, meas_type: str = "tran"
    ) -> None:
        """Configures a measurement to be done in the simulation"""
        self.editor.add_instruction(
            ".meas {} {} {}".format(meas_type, meas_name, meas_expression)
        )
