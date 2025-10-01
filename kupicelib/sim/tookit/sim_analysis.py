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
from collections.abc import Callable, Mapping, Sequence
from functools import wraps
from typing import Any, Literal, Protocol, TypeAlias, cast, overload, runtime_checkable

from ...editor.base_editor import BaseEditor
from ...log.logfile_data import LogfileData
from ...log.ltsteps import LTSpiceLogReader
from ...log.qspice_log_reader import QspiceLogReader
from ...utils.detect_encoding import EncodingDetectError
from ..sim_runner import AnyRunner, ProcessCallback, RunTask

_logger = logging.getLogger("kupicelib.SimAnalysis")


InstructionType = Literal[
    "set_component_value",
    "set_element_model",
    "set_parameter",
    "add_instruction",
    "remove_instruction",
    "remove_Xinstruction",
]

ReceivedInstruction: TypeAlias = (
    tuple[
        Literal["set_component_value", "set_element_model", "set_parameter"],
        str,
        str,
    ]
    | tuple[
        Literal["add_instruction", "remove_instruction", "remove_Xinstruction"],
        str,
    ]
)


@runtime_checkable
class RunnerWithCleanup(Protocol):
    def cleanup_files(self) -> None: ...


class InstructionEditor(Protocol):
    def set_component_value(self, ref: str, value: str) -> None: ...

    def set_element_model(self, ref: str, model: str) -> None: ...

    def set_parameter(self, ref: str, value: str) -> None: ...

    def add_instruction(self, instruction: str) -> None: ...

    def remove_instruction(self, instruction: str) -> None: ...

    def remove_Xinstruction(self, search_pattern: str) -> None: ...


class SimAnalysis:
    """Base class for making Monte-Carlo, Extreme Value Analysis (EVA) or Failure Mode
    and Effects Analysis. As a base class, a certain number of assertions must be made
    on the simulation results that will make the pass/fail.

    Note: For the time being only measurements done with .MEAS are possible. At a later
    stage the parsing of RAW files will be possible, although, it seems that the later
    solution is less computing intense.
    """

    def __init__(
        self, circuit_file: str | BaseEditor, runner: AnyRunner | None = None
    ):
        from ...editor.spice_editor import SpiceEditor

        self.editor: BaseEditor
        if isinstance(circuit_file, str):
            self.editor = SpiceEditor(circuit_file)
        else:
            self.editor = circuit_file
        self._runner: AnyRunner | None = runner
        self.simulations: list[RunTask | None] = []
        self.last_run_number = 0
        self.received_instructions: list[ReceivedInstruction] = []
        self.instructions_added = False
        self.log_data = LogfileData()

    def clear_simulation_data(self):
        """Clears the data from the simulations."""
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
        callback: type[ProcessCallback] | Callable[..., Any] | None = None,
        callback_args: Sequence[Any] | Mapping[str, Any] | None = None,
        switches: Sequence[str] | None = None,
        timeout: float | None = None,
        run_filename: str | None = None,
        exe_log: bool = True,
    ) -> RunTask | None:
        """Runs the simulations.

        See runner.run() method for details on arguments.
        """
        sim = self.runner.run(
            self.editor,
            wait_resource=wait_resource,
            callback=callback,
            callback_args=callback_args,
            switches=switches,
            timeout=timeout,
            run_filename=run_filename,
            exe_log=exe_log,
        )
        if sim is not None:
            self.simulations.append(sim)
            return sim
        return None

    def wait_completion(self):
        self.runner.wait_completion()

    @wraps(BaseEditor.reset_netlist)
    def reset_netlist(self):
        """Resets the netlist to the original state and clears the instructions added by
        the user."""
        self._reset_netlist()
        self.received_instructions.clear()

    def _reset_netlist(self):
        """Unlike the reset_netlist method of the BaseEditor, this method does not clear
        the instructions added by the user.

        This is useful for the case where the user wants to run multiple simulations
        with different parameters without having to add the instructions again.
        """
        self.editor.reset_netlist()
        self.instructions_added = False

    def set_component_value(self, ref: str, new_value: str):
        self.received_instructions.append(("set_component_value", ref, new_value))

    def set_element_model(self, ref: str, new_model: str):
        self.received_instructions.append(("set_element_model", ref, new_model))

    def set_parameter(self, ref: str, new_value: str):
        self.received_instructions.append(("set_parameter", ref, new_value))

    def add_instruction(self, new_instruction: str):
        self.received_instructions.append(("add_instruction", new_instruction))

    def remove_instruction(self, instruction: str):
        self.received_instructions.append(("remove_instruction", instruction))

    def remove_Xinstruction(self, search_pattern: str):
        self.received_instructions.append(("remove_Xinstruction", search_pattern))

    def play_instructions(self):
        if self.instructions_added:
            return  # Nothing to do
        editor = cast(InstructionEditor, self.editor)
        for instruction in self.received_instructions:
            tag = instruction[0]
            if tag == "set_component_value":
                _, ref, value = cast(
                    tuple[Literal["set_component_value"], str, str], instruction
                )
                editor.set_component_value(ref, value)
            elif tag == "set_element_model":
                _, ref, model = cast(
                    tuple[Literal["set_element_model"], str, str], instruction
                )
                editor.set_element_model(ref, model)
            elif tag == "set_parameter":
                _, ref, value = cast(
                    tuple[Literal["set_parameter"], str, str], instruction
                )
                editor.set_parameter(ref, value)
            elif tag == "add_instruction":
                _, value = cast(
                    tuple[Literal["add_instruction"], str], instruction
                )
                editor.add_instruction(value)
            elif tag == "remove_instruction":
                _, value = cast(
                    tuple[Literal["remove_instruction"], str], instruction
                )
                editor.remove_instruction(value)
            elif tag == "remove_Xinstruction":
                _, value = cast(
                    tuple[Literal["remove_Xinstruction"], str], instruction
                )
                editor.remove_Xinstruction(value)
            else:
                raise ValueError(f"Unknown instruction tag: {tag}")
        self.instructions_added = True

    def save_netlist(self, filename: str):
        self.play_instructions()
        self.editor.save_netlist(filename)

    def cleanup_files(self) -> None:
        """Clears all simulation files.

        Typically used after a simulation run and analysis.
        """
        runner = self.runner
        if isinstance(runner, RunnerWithCleanup):
            runner.cleanup_files()

    def simulation(self, index: int) -> RunTask | None:
        """Returns a simulation object."""
        return self.simulations[index]

    @overload
    def __getitem__(self, item: int) -> RunTask | None: ...

    @overload
    def __getitem__(self, item: slice) -> list[RunTask | None]: ...

    def __getitem__(self, item: int | slice) -> RunTask | None | list[RunTask | None]:
        return self.simulations[item]

    @staticmethod
    def read_logfile(run_task: RunTask) -> LogfileData | None:
        """Reads the log file and returns a dictionary with the results."""
        log_reader_cls: type[LTSpiceLogReader | QspiceLogReader]
        if run_task.simulator.__name__ == "LTspice":
            log_reader_cls = LTSpiceLogReader
        elif run_task.simulator.__name__ == "Qspice":
            log_reader_cls = QspiceLogReader
        else:
            raise ValueError("Unknown simulator type")

        try:
            # Ensure log_file is not None before passing it to LogReader
            if run_task.log_file is None:
                _logger.warning("Log file is None")
                return None
            log_results = log_reader_cls(str(run_task.log_file))
        except FileNotFoundError:
            _logger.warning("Log file not found: %s", run_task.log_file)
            return None
        except EncodingDetectError:
            _logger.warning("Log file %s couldn't be read", run_task.log_file)
            return None
        return log_results

    def add_log_data(self, log_data: LogfileData) -> None:
        """Add data from a log file to the log_data object."""
        for param, values in log_data.stepset.items():
            if param not in self.log_data.stepset:
                self.log_data.stepset[param] = list(values)
            else:
                self.log_data.stepset[param].extend(values)
        for param, dataset_values in log_data.dataset.items():
            if param not in self.log_data.dataset:
                self.log_data.dataset[param] = list(dataset_values)
            else:
                self.log_data.dataset[param].extend(dataset_values)
        self.log_data.step_count += log_data.step_count

    def read_logfiles(self) -> LogfileData:
        """Reads the log files and returns a dictionary with the results."""
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
    ):
        """Configures a measurement to be done in the simulation."""
        self.editor.add_instruction(
            f".meas {meas_type} {meas_name} {meas_expression}"
        )
