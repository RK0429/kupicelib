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
# Name:        sim_stepping.py
# Purpose:     Spice Simulation Library intended to automate the exploring of
#              design corners, try different models and different parameter
#              settings.
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     31-07-2020
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2017, Fribourg Switzerland"

import logging
from collections.abc import Iterable, Iterator, Mapping, Sequence, Sized
from typing import Any, Generic, Literal, Protocol, TypeVar, cast

from ..editor.base_editor import BaseEditor
from .sim_runner import AnyRunner, CallbackType

_logger = logging.getLogger("kupicelib.SimStepper")


StepValue = TypeVar("StepValue")


class StepInfo(Generic[StepValue]):
    def __init__(self, what: str, elem: str, iterable: Iterable[StepValue]) -> None:
        self.what = what
        self.elem = elem
        self._iterable: Iterable[StepValue] = iterable
        self._cached_sequence: Sequence[StepValue] | None = (
            iterable if isinstance(iterable, Sequence) else None
        )

    @property
    def iter(self) -> Iterable[StepValue]:
        return self._cached_sequence if self._cached_sequence is not None else self._iterable

    @iter.setter
    def iter(self, iterable: Iterable[StepValue]) -> None:
        self._iterable = iterable
        self._cached_sequence = iterable if isinstance(iterable, Sequence) else None

    def __len__(self) -> int:
        if self._cached_sequence is not None:
            return len(self._cached_sequence)
        if isinstance(self._iterable, Sized):
            sized_iterable = cast(Sized, self._iterable)
            return len(sized_iterable)
        materialized = tuple(self._iterable)
        self._cached_sequence = materialized
        self._iterable = materialized
        return len(materialized)

    def __str__(self) -> str:
        return f"Iteration on {self.what} {self.elem} : {self.iter}"


class RunnerWithStats(AnyRunner, Protocol):
    @property
    def okSim(self) -> int:
        ...

    @property
    def runno(self) -> int:
        ...


class InstructionEditor(Protocol):
    def add_instructions(self, *instructions: str) -> None:
        ...

    def remove_instruction(self, instruction: str) -> None:
        ...

    def remove_Xinstruction(self, search_pattern: str) -> None:
        ...

    def set_parameters(self, **kwargs: str | int | float) -> None:
        ...

    def set_component_values(self, **kwargs: str | int | float) -> None:
        ...


class SimStepper:
    """This class is intended to be used for simulations with many parameter sweeps.
    This provides a more user-friendly interface than the SpiceEditor/SimRunner class
    when there are many parameters to be stepped.

    Using the SpiceEditor/SimRunner classes a loop needs to be added for each dimension
    of the simulations. A typical usage would be as follows: ``` netlist =
    SpiceEditor("my_circuit.asc") runner = SimRunner(parallel_sims=4) for dmodel in
    ("BAT54", "BAT46WJ")     netlist.set_element_model("D1", model)  # Sets the Diode D1
    model     for res_value1 in sweep(2.2, 2,4, 0.2):  # Steps from 2.2 to 2.4 with 0.2
    increments         netlist.set_component_value('R1', res_value1)  # Updates the
    resistor R1 value to be 3.3k         for temperature in sweep(0, 80, 20):  # Makes
    temperature step from 0 to 80 degrees in 20 degree steps
    netlist.set_parameters(temp=80)  # Sets the simulation temperature to be 80 degrees
    for res_value2 in (10, 25, 32):                 netlist.set_component_value('R2',
    res_value2)  # Updates the resistor R2 value to be 3.3k runner.run(netlist)

    runner.wait_completion()  # Waits for the Spice simulations to complete ```

    With SimStepper the same thing can be done as follows, resulting in a cleaner code.

    ``` netlist = SpiceEditor("my_circuit.asc") Stepper = SimStepper(netlist,
    SimRunner(parallel_sims=4, output_folder="./output")) Stepper.add_model_sweep('D1',
    "BAT54", "BAT46WJ") Stepper.add_component_sweep('R1', sweep(2.2, 2,4, 0.2))  # Steps
    from 2.2 to 2.4 with 0.2 increments Stepper.add_parameter_sweep('temp', sweep(0, 80,
    20))  # Makes temperature step from 0 to 80 degrees in 20 # degree steps
    Stepper.add_component_sweep('R2', (10, 25, 32)) #  Updates the resistor R2 value to
    be 3.3k Stepper.run_all()

    ```

    Another advantage of using SimStepper is that it can optionally use the .SAVEBIAS in
    the first simulation and then use the .LOADBIAS command at the subsequent ones to
    speed up the simulation times.
    """

    def __init__(self, circuit: BaseEditor, runner: RunnerWithStats):
        self.runner: RunnerWithStats = runner
        self.netlist: BaseEditor = circuit
        self._instruction_editor: InstructionEditor = cast(InstructionEditor, circuit)
        self.iter_list: list[StepInfo[Any]] = []

    def add_instruction(self, instruction: str) -> None:
        self.netlist.add_instruction(instruction)

    def add_instructions(self, *instructions: str) -> None:
        self._instruction_editor.add_instructions(*instructions)

    def remove_instruction(self, instruction: str) -> None:
        self._instruction_editor.remove_instruction(instruction)

    def remove_Xinstruction(self, search_pattern: str) -> None:
        self._instruction_editor.remove_Xinstruction(search_pattern)

    def set_parameters(self, **kwargs: str | int | float) -> None:
        self._instruction_editor.set_parameters(**kwargs)

    def set_parameter(self, param: str, value: str | int | float) -> None:
        self.netlist.set_parameter(param, value)

    def set_component_values(self, **kwargs: str | int | float) -> None:
        self._instruction_editor.set_component_values(**kwargs)

    def set_component_value(self, device: str, value: str | int | float) -> None:
        self.netlist.set_component_value(device, value)

    def set_element_model(self, element: str, model: str) -> None:
        self.netlist.set_element_model(element, model)

    def add_param_sweep(self, param: str, iterable: Iterable[Any]) -> None:
        """Adds a dimension to the simulation, where the param is swept."""
        self.iter_list.append(StepInfo("param", param, iterable))

    def add_value_sweep(self, comp: str, iterable: Iterable[Any]) -> None:
        """Adds a dimension to the simulation, where a component value is swept."""
        # The next line raises an ComponentNotFoundError if the component doesn't exist
        _ = self.netlist.get_component_value(comp)
        self.iter_list.append(StepInfo("component", comp, iterable))

    def add_model_sweep(self, comp: str, iterable: Iterable[Any]) -> None:
        """Adds a dimension to the simulation, where a component model is swept."""
        # The next line raises an ComponentNotFoundError if the component doesn't exist
        _ = self.netlist.get_component_value(comp)
        self.iter_list.append(StepInfo("model", comp, iterable))

    def total_number_of_simulations(self) -> int:
        """Returns the total number of simulations foreseen."""
        total = 1
        for step in self.iter_list:
            step_length = len(step)
            if step_length:
                total *= step_length
            else:
                _logger.debug(f"'{step}' is empty.")
        return total

    def run_all(
        self,
        callback: CallbackType | None = None,
        callback_args: Sequence[Any] | Mapping[str, Any] | None = None,
        switches: Sequence[str] | None = None,
        timeout: float | None = None,
        use_loadbias: Literal["Auto", "Yes", "No"] = "Auto",
        wait_completion: bool = True,
    ) -> None:
        assert use_loadbias in (
            "Auto",
            "Yes",
            "No",
        ), "use_loadbias argument must be 'Auto', 'Yes' or 'No'"
        if (
            use_loadbias == "Auto" and self.total_number_of_simulations() > 10
        ) or use_loadbias == "Yes":
            # Use .SAVEBIAS/.LOADBIAS when more than 10 simulations are required.
            # TODO: Make a first simulation and storing the bias
            pass
        iter_no = 0
        iterators: list[Iterator[Any]] = [iter(step.iter) for step in self.iter_list]
        while True:
            while 0 <= iter_no < len(self.iter_list):
                try:
                    value = next(iterators[iter_no])
                except StopIteration:
                    iterators[iter_no] = iter(self.iter_list[iter_no].iter)
                    iter_no -= 1
                    continue
                if self.iter_list[iter_no].what == "param":
                    self.netlist.set_parameter(self.iter_list[iter_no].elem, value)
                elif self.iter_list[iter_no].what == "component":
                    self.netlist.set_component_value(
                        self.iter_list[iter_no].elem, value
                    )
                elif self.iter_list[iter_no].what == "model":
                    self.netlist.set_element_model(self.iter_list[iter_no].elem, value)
                else:
                    # TODO: develop other types of sweeps EX: add .STEP instruction
                    raise ValueError("Not Supported sweep")
                iter_no += 1
            if iter_no < 0:
                break
            self.runner.run(
                self.netlist,
                callback=callback,
                callback_args=callback_args,
                switches=switches,
                timeout=timeout,
            )  # Like this a recursion is avoided
            iter_no = (
                len(self.iter_list) - 1
            )  # Resets the counter to start next iteration
        if wait_completion:
            # Now waits for the simulations to end
            self.runner.wait_completion()

    def run(self):
        """Rather uses run_all instead."""
        self.run_all()

    @property
    def okSim(self) -> int:
        return self.runner.okSim

    @property
    def runno(self) -> int:
        return self.runner.runno


if __name__ == "__main__":
    from kupicelib.editor.spice_editor import SpiceEditor
    from kupicelib.sim.sim_runner import SimRunner
    from kupicelib.utils.sweep_iterators import sweep_log

    # Correct example for demonstration purposes
    netlist = SpiceEditor("../../tests/DC sweep.asc")
    runner = SimRunner()
    test = SimStepper(cast(BaseEditor, netlist), cast(RunnerWithStats, runner))
    # The set_parameter method is decorated with @wraps which causes type checking issues
    # in the test code, but it works correctly at runtime
    netlist.set_parameter("R1", 3)  # Set parameter on the netlist directly
    test.add_param_sweep("res", [10, 11, 9])
    test.add_value_sweep("R1", sweep_log(0.1, 10))
    # test.add_model_sweep("D1", ("model1", "model2"))
    test.run_all()
    print("Finished")
    exit(0)
