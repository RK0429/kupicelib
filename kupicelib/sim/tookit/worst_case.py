#!/usr/bin/env python
from __future__ import annotations
# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        worst_case.py
# Purpose:     Class to automate Worst-Case simulations
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     10-08-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

import logging
from collections.abc import Callable, Iterable
from typing import Any, cast

from ...log.logfile_data import LogfileData
from ..process_callback import ProcessCallback
from .tolerance_deviations import DeviationType, ToleranceDeviations

_logger = logging.getLogger("kupicelib.SimAnalysis")


class WorstCaseAnalysis(ToleranceDeviations):
    """Class to automate Worst-Case simulations, where all possible combinations of
    maximum and minimums possible values of component values and parameters are done.

    It is advised to use this algorithm when the number of parameters to be varied is
    reduced. Typically less than 10 or 12. A higher number will translate into a huge
    number of simulations. For more than 1000 simulations, it is better to use a
    statistical method such as the Montecarlo.

    Like the Montecarlo and Sensitivity analysis, there are two possible approaches to
    use this class:

    1. Preparing a testbench where all combinations are managed directly by the
    simulator, replacing  parameters and component values by formulas and using a .STEP
    primitive to cycle through all possible  combinations.

    2. Launching each simulation separately where the running python script manages all
    parameter value variations.

    The first approach is normally faster, but not possible in all simulators. The
    second approach is a valid backup when every single simulation takes too long, or
    when it is prone to crashes and stalls.
    """

    def _set_component_deviation(self, ref: str, index: int) -> bool:
        """Sets the deviation of a component.

        Returns True if the component is valid and the deviation was set. Otherwise,
        returns False
        """
        val, dev = self.get_component_value_deviation_type(
            ref
        )  # get there present value
        if dev.min_val == dev.max_val:
            return False  # no need to set the deviation
        new_val = val
        if dev.typ == DeviationType.tolerance:
            new_val = f"{{wc({val},{dev.max_val:g},{index})}}"
        elif dev.typ == DeviationType.minmax:
            new_val = (
                f"{{wc1({val},{dev.min_val:g},{dev.max_val:g},{index})}}"
            )  # calculate expression for new value

        if new_val != val:
            self.set_component_value(ref, str(new_val))  # update the value
            self.elements_analysed.append(ref)
        return True

    def prepare_testbench(self, **kwargs: Any) -> None:
        """Prepares the simulation by setting the tolerances for the components."""
        index = 0
        self.elements_analysed.clear()
        device_refs: list[str] = [str(key) for key in self.device_deviations.keys()]
        for ref in device_refs:
            if self._set_component_deviation(ref, index):
                index += 1
        parameter_refs: list[str] = [
            str(key) for key in self.parameter_deviations.keys()
        ]
        for ref in parameter_refs:
            val, dev = self.get_parameter_value_deviation_type(ref)
            new_val = val
            if dev.typ == DeviationType.tolerance:
                new_val = f"{{wc({val},{dev.max_val:g},{index})}}"
            elif dev.typ == DeviationType.minmax:
                new_val = (
                    f"{{wc1({val},{dev.min_val:g},{dev.max_val:g},{index})}}"
                )
            if new_val != val:
                self.editor.set_parameter(ref, str(new_val))
            index += 1
            self.elements_analysed.append(ref)

        for prefix in self.default_tolerance:
            components_iter = cast(Iterable[str], self.get_components(prefix))
            components_list = list(components_iter)
            for component in components_list:
                ref = component
                if ref not in self.device_deviations:
                    if self._set_component_deviation(ref, index):
                        index += 1

        self.editor.add_instruction(
            ".func binary(run,idx) {floor(run/(2**idx))-2*floor(run/(2**(idx+1)))}"
        )
        self.editor.add_instruction(
            ".func wc(nom,tol,idx) {if(run<0,nom,nom*(1+tol*(2*binary(run,idx)-1)))}"
        )
        self.editor.add_instruction(
            ".func wc1(nom,min,max,idx) {if(run<0, nom, if(binary(run,idx),max,min))}"
        )
        self.last_run_number = 2**index - 1
        self.editor.add_instruction(
            f".step param run -1 {self.last_run_number} 1"
        )
        self.editor.set_parameter("run", -1)  # in case the step is commented.
        self.testbench_prepared = True

    def run_analysis(
        self,
        callback: type[ProcessCallback] | Callable[..., Any] | None = None,
        callback_args: tuple[Any, ...] | dict[str, Any] | None = None,
        switches: list[str] | None = None,
        timeout: float | None = None,
        exe_log: bool = True,
    ) -> None:
        """This method runs the analysis without updating the netlist.

        It will update component values and parameters according to their deviation type
        and call the simulation. The advantage of this method is that it doesn't require
        adding random functions to the netlist.
        """
        self.clear_simulation_data()
        self.elements_analysed.clear()
        worst_case_elements: dict[str, tuple[Any, Any, str]] = {}

        def check_and_add_component(ref1: str) -> None:
            val1, dev1 = self.get_component_value_deviation_type(
                ref1
            )  # get there present value
            if dev1.min_val == dev1.max_val or dev1.typ == DeviationType.none:
                return
            worst_case_elements[ref1] = val1, dev1, "component"
            self.elements_analysed.append(ref1)

        device_refs_analysis: list[str] = [
            str(key) for key in self.device_deviations.keys()
        ]
        for ref in device_refs_analysis:
            check_and_add_component(ref)

        parameter_refs_analysis: list[str] = [
            str(key) for key in self.parameter_deviations.keys()
        ]
        for ref in parameter_refs_analysis:
            val, dev = self.get_parameter_value_deviation_type(ref)
            if dev.typ == DeviationType.tolerance or dev.typ == DeviationType.minmax:
                worst_case_elements[ref] = val, dev, "parameter"
                self.elements_analysed.append(ref)

        for prefix in self.default_tolerance:
            components_iter = cast(Iterable[str], self.get_components(prefix))
            components_list = list(components_iter)
            for ref_value in components_list:
                if ref_value not in self.device_deviations:
                    check_and_add_component(ref_value)

        _logger.info(
            "Worst Case Analysis: %d elements to be analysed",
            len(self.elements_analysed),
        )

        # Calculate the number of runs
        run_count = 2 ** len(self.elements_analysed)
        self.last_run_number = run_count - 1

        _logger.info("Worst Case Analysis: %d runs to be executed", run_count)
        if run_count >= 4096:
            _logger.warning(
                "The number of runs is too high. It will be limited to 4096\n"
                "Consider limiting the number of components with deviation"
            )
            return

        self._reset_netlist()  # reset the netlist
        self.play_instructions()  # play the instructions
        self.editor.set_parameter(
            "run", -1
        )  # This is aligned with the testbench preparation
        self.editor.add_instruction(".meas runm PARAM {run}")
        # Simulate the nominal case
        self.run(
            wait_resource=True,
            callback=callback,
            callback_args=callback_args,
            switches=switches,
            timeout=timeout,
            exe_log=exe_log,
        )
        self.runner.wait_completion()
        # Simulate the worst case
        last_run = self.last_run_number  # Sets all valid bits to 1
        for run in range(0, run_count):
            # Preparing the variation on components, but only on the ones that have
            # changed
            bit_updated = run ^ last_run
            bit_index = 0
            while bit_updated != 0:
                if bit_updated & 1:
                    ref = self.elements_analysed[bit_index]
                    val, dev, typ = worst_case_elements[ref]
                    if dev.typ == DeviationType.tolerance:
                        new_val = (
                            val * (1 - dev.max_val)
                            if run & (1 << bit_index)
                            else val * (1 + dev.max_val)
                        )
                    elif dev.typ == DeviationType.minmax:
                        new_val = dev.min_val if run & (1 << bit_index) else dev.max_val
                    else:
                        _logger.warning("Unknown deviation type")
                        new_val = val
                    if typ == "component":
                        self.editor.set_component_value(
                            ref, str(new_val)
                        )  # update the value
                    elif typ == "parameter":
                        self.editor.set_parameter(ref, str(new_val))
                    else:
                        _logger.warning("Unknown type")
                bit_updated >>= 1
                bit_index += 1

            self.editor.set_parameter("run", run)
            # Run the simulation
            self.run(
                wait_resource=True,
                callback=callback,
                callback_args=callback_args,
                switches=switches,
                timeout=timeout,
                exe_log=exe_log,
            )
            last_run = run
        self.runner.wait_completion()

        if callback is not None:
            callback_rets: list[Any] = []
            for rt in self.simulations:
                if rt is not None:
                    callback_rets.append(rt.get_results())
            self.simulation_results["callback_returns"] = callback_rets
        self.analysis_executed = True

    def get_min_max_measure_value(self, meas_name: str) -> tuple[float, float] | None:
        """Returns the minimum and maximum values of a measurement.

        See SPICE .MEAS primitive documentation.
        """
        if not self.analysis_executed:
            _logger.warning(
                "The analysis was not executed. Please run the analysis before calling this method"
            )
            return None

        log_data: LogfileData = self.read_logfiles()
        meas_data: list[Any] = log_data[meas_name]
        if len(meas_data) != len(self.simulations):
            _logger.warning(
                "Missing log files. Results may not be reliable. Probable cause are:\n"
                "  - Failed simulations.\n"
                "  - Measurement couldn't be done in simulation results."
            )
        numeric_values: list[float] = []
        for value in meas_data:
            if isinstance(value, (int, float)):
                numeric_values.append(float(value))
            elif isinstance(value, complex):
                numeric_values.append(abs(value))
        if not numeric_values:
            _logger.warning("Measurement %s does not contain numeric data", meas_name)
            return None
        return min(numeric_values), max(numeric_values)

    def make_sensitivity_analysis(
        self, measure: str, ref: str = "*"
    ) -> dict[str, tuple[float, float]] | tuple[float, float] | None:
        """Makes a sensitivity analysis for a given measurement and reference component.
        The sensitivity is a percentage of the component error contribution over the
        total error. As supplement a second value is given that is the standard
        deviation of the error contribution of the component across all sensitivity
        analysis simulations.

        If no reference is given, it will return a dictionary where the key is the
        component reference and the value is the tuple with (sensitivity,
        standard_deviation) in percent values of the total error.

        Returns None, if no data still exists for the sensitivity analysis.

        :param measure: measurement name. See SPICE .MEAS primitive
        :type measure: str
        :param ref: Optional component reference in the netlist
        :type ref: str
        :returns: Tuple with sensitivity and a standard deviation or dictionary of
            tuples.
        """
        if (
            (self.testbench_prepared
            and self.testbench_executed)
            or self.analysis_executed
        ):
            # Read the log files
            log_data: LogfileData = self.read_logfiles()

            def measure_at(step_index: int) -> float | int | complex | str:
                result = log_data.get_measure_value(measure, step=step_index)
                return cast(float | int | complex | str, result)

            wc_data: list[float | complex] = []
            for run_idx in range(self.last_run_number + 1):
                value = measure_at(run_idx)
                if isinstance(value, (int, float)):
                    wc_data.append(float(value))
                elif isinstance(value, complex):
                    wc_data.append(value)
                else:
                    try:
                        wc_data.append(float(value))
                    except (TypeError, ValueError):
                        _logger.debug(
                            "Non-numeric measurement '%s' ignored for run %d",
                            value,
                            run_idx,
                        )
            if not wc_data:
                _logger.warning("No numeric data found for measure %s", measure)
                return None

            def diff_for_a_ref(
                values: list[float | complex], bit_index: int
            ) -> tuple[float, float]:
                """Calculates the difference of the measurement for the toggle of a
                given bit."""

                bit_updated = 1 << bit_index
                diffs: list[float] = []
                for run_idx in range(len(values)):
                    if run_idx & bit_updated == 0:
                        base_val = values[run_idx]
                        toggled_val = values[run_idx | bit_updated]
                        diffs.append(abs(base_val - toggled_val))
                if not diffs:
                    return 0.0, 0.0
                mean = sum(diffs) / len(diffs)
                variance = sum((diff - mean) ** 2 for diff in diffs) / len(diffs)
                std_div = variance**0.5
                return mean, std_div

            sensitivities: dict[str, tuple[float, float]] = {}
            for idx, ref_name in enumerate(self.elements_analysed):
                sensitivities[ref_name] = diff_for_a_ref(wc_data, idx)
            total = sum(sens[0] for sens in sensitivities.values())
            if total == 0:
                return None

            # Calculate the sensitivity for each component if ref is '*'
            # Return the sensitivity as a percentage of the total error
            # This is not very accurate, but it is a way of having
            # sensitivity as a percentages that sum up to 100%.
            if ref == "*":
                # Returns a dictionary with all the references sensitivity
                answer: dict[str, tuple[float, float]] = {}
                for ref_name, (sens, sigma) in sensitivities.items():
                    answer[ref_name] = sens / total * 100, sigma / total * 100
                return answer
            else:
                # Calculates the sensitivity for the given component
                if ref not in sensitivities:
                    _logger.warning("Reference %s not part of sensitivity set", ref)
                    return None
                sens, sigma = sensitivities[ref]
                return sens / total * 100, sigma / total * 100
        else:
            _logger.warning(
                "The analysis was not executed. Run run_analysis(...) or "
                "run_testbench(...) before calling this method."
            )
            return None
