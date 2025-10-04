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
# Name:        quick_sensitivity_analysis.py
# Purpose:     Classes to make a sensitivity analysis
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     16-10-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal, cast

from ...editor.base_editor import BaseEditor, scan_eng
from ...log.logfile_data import LogfileData, LTComplex, ValueType
from ..sim_runner import AnyRunner, ProcessCallback
from .tolerance_deviations import (
    ComponentDeviation,
    DeviationType,
    ToleranceDeviations,
)

_logger = logging.getLogger("kupicelib.SimAnalysis")

WorstCaseType = Literal["component", "parameter"]
WorstCaseEntry = tuple[str | float, ComponentDeviation, WorstCaseType]
CallbackArgs = tuple[Any, ...] | dict[str, Any]


def _value_to_float(value: ValueType) -> float | None:
    """Convert a measurement value to a float when possible."""
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, LTComplex):
        return float(value.real)
    if isinstance(value, str):
        try:
            return float(scan_eng(value))
        except ValueError:
            return None
    return None


class QuickSensitivityAnalysis(ToleranceDeviations):
    """Class to automate Sensitivity simulations."""

    def __init__(
        self, circuit_file: str | BaseEditor, runner: AnyRunner | None = None
    ):
        super().__init__(circuit_file, runner)

    def prepare_testbench(self, **kwargs: Any) -> None:
        """Prepares the simulation by setting the tolerances for each component."""
        no = 0
        self.elements_analysed.clear()
        use_min = kwargs.get("use_min", False)
        for comp in self.get_components("*"):
            val, dev = self.get_component_value_deviation_type(comp)
            new_val = val
            if dev.typ == DeviationType.tolerance:
                new_val = f"{{satol({val},{dev.max_val:g},{no})}}"
            elif dev.typ == DeviationType.minmax:
                used_value = dev.min_val if use_min else dev.max_val
                new_val = f"{{sammx({val},{used_value:g},{no})}}"

            if new_val != val:
                self.set_component_value(comp, str(new_val))
                self.elements_analysed.append(comp)
                no += 1

        self.last_run_number = no - 1
        if use_min:
            self.editor.add_instruction(
                ".func satol(nom,tol,idx) nom*if(run==idx,1-tol,1)"
            )
        else:
            self.editor.add_instruction(
                ".func satol(nom,tol,idx) nom*if(run==idx,1+tol,1)"
            )
        self.editor.add_instruction(".func sammx(nom,val,idx) if(run==idx,val,nom)")
        self.editor.add_instruction(
            f".step param run -1 {self.last_run_number} 1"
        )
        self.editor.set_parameter("run", -1)  # in case the step is commented.
        self.testbench_prepared = True

    def get_sensitivity_data(
        self, ref: str, measure: str
    ) -> float | dict[str, float] | None:
        """Returns the sensitivity data for a given component and measurement in terms
        of percentage of the total error.

        This quick approach is not very accurate, but it is fast. It assumes that the
        system is linear and that the maximum error is the sum of the absolute error of
        each component. This is a rough approximation, but it is good enough for a quick
        analysis. For more accurate results, use the Worst Case Analysis, which requires
        more simulation runs but gives a more accurate result. The best compromise, is
        to start with the quick analysis and then use the Worst Case Analysis to refine
        the results with only the components that have a significant contribution to the
        error.
        :param ref: The reference component, or '*' to return a dictionary with all the
            components
        :param measure: The measurement to be analysed
        :return: The sensitivity data in percentage of the total error for the reference
            component
        """
        if (
            (self.testbench_prepared
            and self.testbench_executed)
            or self.analysis_executed
        ):
            log_data: LogfileData = self.read_logfiles()
            nominal_data = log_data.get_measure_value(measure, run=-1)
            error_data: list[float] = []
            for idx in range(len(self.elements_analysed)):
                step_data = log_data.get_measure_value(measure, run=idx)
                nom_val = _value_to_float(nominal_data)
                step_val = _value_to_float(step_data)
                if nom_val is None or step_val is None:
                    error_data.append(0.0)
                    continue
                error_data.append(abs(step_val - nom_val))
            total_error = sum(error_data)
            if ref == "*":
                return {
                    ref: error_data[idx] / total_error * 100 if total_error != 0 else 0
                    for idx, ref in enumerate(self.elements_analysed)
                }
            else:
                idx = self.elements_analysed.index(ref)
                return error_data[idx] / total_error * 100 if total_error != 0 else 0
        else:
            _logger.warning(
                "The analysis was not executed. Run run_analysis(...) or "
                "run_testbench(...) before calling this method."
            )
            return None

    def run_analysis(
        self,
        callback: type[ProcessCallback] | Callable[..., Any] | None = None,
        callback_args: Sequence[Any] | Mapping[str, Any] | None = None,
        switches: Sequence[str] | None = None,
        timeout: float | None = None,
        exe_log: bool = True,
    ) -> None:
        self.clear_simulation_data()
        self.elements_analysed.clear()
        # Calculate the number of runs

        worst_case_elements: dict[str, WorstCaseEntry] = {}

        def check_and_add_component(ref1: str):
            val1, dev1 = self.get_component_value_deviation_type(
                ref1
            )  # get there present value
            if dev1.min_val == dev1.max_val or dev1.typ == DeviationType.none:
                return
            worst_case_elements[ref1] = val1, dev1, "component"
            self.elements_analysed.append(ref1)

        for ref in self.device_deviations:
            check_and_add_component(ref)

        for ref in self.parameter_deviations:
            val, dev = self.get_parameter_value_deviation_type(ref)
            if dev.typ == DeviationType.tolerance or dev.typ == DeviationType.minmax:
                worst_case_elements[ref] = (val, dev, "parameter")
                self.elements_analysed.append(ref)

        for prefix in self.default_tolerance:
            for ref in self.get_components(prefix):
                if ref not in self.device_deviations:
                    check_and_add_component(ref)

        last_run_number = len(self.elements_analysed)
        if last_run_number > 4096:
            _logger.warning(
                "The number of runs is too high. It will be limited to 4096\n"
                "Consider limiting the number of components with deviation"
            )
            return

        self._reset_netlist()  # reset the netlist
        self.play_instructions()  # play the instructions
        # Add the run number to the measurements by using a parameter
        self.editor.set_parameter("run", -1)  # in case the step is commented.
        self.editor.add_instruction(".meas runm PARAM {run}")
        # Run the simulation in the nominal case
        # Handle optional parameters to match required types
        def _noop_callback(*_args: Any, **_kwargs: Any) -> None:
            return None

        actual_callback: type[ProcessCallback] | Callable[..., Any]
        actual_callback = callback if callback is not None else _noop_callback

        if callback_args is None:
            actual_callback_args: CallbackArgs = ()
        elif isinstance(callback_args, Mapping):
            actual_callback_args = dict(callback_args)
        elif isinstance(callback_args, str | bytes):
            actual_callback_args = (callback_args,)
        else:
            actual_callback_args = tuple(callback_args)

        switches_seq = list(switches) if switches is not None else None
        actual_timeout = timeout

        self.run(
            wait_resource=True,
            callback=actual_callback,
            callback_args=actual_callback_args,
            switches=switches_seq,
            timeout=actual_timeout,
            exe_log=exe_log,
        )
        last_bit_setting = 0
        for run in range(last_run_number):
            # Preparing the variation on components, but only on the ones that have
            # changed
            bit_setting = 2**run
            bit_updated = bit_setting ^ last_bit_setting
            bit_index = 0
            print(f"bit updated: {bit_updated}")
            while bit_updated != 0:
                if bit_updated & 1:
                    ref = self.elements_analysed[bit_index]
                    val, dev, typ = worst_case_elements[ref]
                    new_val: float | str
                    if dev.typ == DeviationType.tolerance:
                        base_val = val
                        if not isinstance(base_val, int | float):
                            try:
                                base_val = float(base_val)
                            except (TypeError, ValueError):
                                _logger.warning(
                                    "Value %s for %s is not numeric; skipping deviation",
                                    base_val,
                                    ref,
                                )
                                base_val = val
                        if isinstance(base_val, int | float):
                            new_val = (
                                float(base_val) * (1 + dev.max_val)
                                if bit_setting & (1 << bit_index)
                                else float(base_val)
                            )
                        else:
                            new_val = base_val
                    elif dev.typ == DeviationType.minmax:
                        new_val = (
                            dev.max_val if bit_setting & (1 << bit_index) else val
                        )
                    else:
                        _logger.warning("Unknown deviation type")
                        new_val = val
                    if typ == "component":
                        self.editor.set_component_value(ref, new_val)
                    elif typ == "parameter":
                        self.editor.set_parameter(ref, new_val)
                    else:
                        _logger.warning("Unknown type")
                    print(f"{ref} = {new_val}")
                bit_updated >>= 1
                bit_index += 1
            self.editor.set_parameter("run", run)
            # Run the simulation
            self.run(
                wait_resource=True,
                callback=actual_callback,
                callback_args=actual_callback_args,
                switches=switches_seq,
                timeout=actual_timeout,
                exe_log=exe_log,
            )
            last_bit_setting = bit_setting
        self.runner.wait_completion()

        if callback is not None:
            callback_rets: list[Any] = []
            for rt in self.simulations:
                if rt is not None:
                    callback_rets.append(rt.get_results())
                else:
                    callback_rets.append(None)
            self.simulation_results["callback_returns"] = callback_rets
        self.analysis_executed = True
        # Force already the reading of logfiles
        log_data: LogfileData = self.read_logfiles()
        # if applicable, the run parameter shall be transformed into an int
        runs: list[Any] = []

        # Access dataset safely
        if hasattr(log_data, "dataset"):
            dataset_raw = getattr(log_data, "dataset", None)
            if isinstance(dataset_raw, dict):
                dataset = cast(dict[str, list[Any]], dataset_raw)
                runm_list: list[Any] = dataset.get("runm", [])
                for run_val in runm_list:
                    if isinstance(run_val, complex):
                        runs.append(round(run_val.real))
                    else:
                        runs.append(run_val)

                if "runm" in dataset:
                    dataset["run"] = runs
            else:
                _logger.warning("Could not process dataset in expected way")
