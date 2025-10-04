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
# Name:        fast_worst_case.py
# Purpose:     Class to automate Worst-Case simulations (Faster Algorithm)
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     04-11-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from enum import IntEnum
from typing import Any, Literal, NamedTuple

from ...log.logfile_data import LogfileData
from ..process_callback import ProcessCallback
from .tolerance_deviations import ComponentDeviation, DeviationType
from .worst_case import WorstCaseAnalysis

_logger = logging.getLogger("kupicelib.SimAnalysis")

CallbackType = type[ProcessCallback] | Callable[..., Any]
CallbackArgs = Sequence[Any] | Mapping[str, Any] | None
SwitchesArg = Sequence[str] | None


class WorstCaseSummary(NamedTuple):
    """Summary of fast worst-case analysis results."""

    nominal: float
    minimum: float
    max_components: dict[str, float]
    maximum: float
    min_components: dict[str, float]


class WorstCaseType(IntEnum):
    nom = 0
    max = 1
    min = 2


class FastWorstCaseAnalysis(WorstCaseAnalysis):
    """Faster algorithm to perform a worst-case analysis.

    The classical approach evaluates all possible deviation combinations which is
    exponential on the number of elements. This implementation estimates the best and
    worst case by iteratively adjusting components according to the sensitivity of the
    monitored measurement.
    """

    last_summary: WorstCaseSummary | None

    def run_testbench(
        self,
        *,
        runs_per_sim: int | None = None,  # pragma: no cover - kept for API parity
        wait_resource: bool = True,  # pragma: no cover - kept for API parity
        callback: CallbackType | None = None,
        callback_args: CallbackArgs = None,
        switches: SwitchesArg = None,
        timeout: float | None = None,
        run_filename: str | None = None,
        exe_log: bool = False,
    ) -> None:
        raise NotImplementedError("run_testbench() is not implemented in this class")

    def run_analysis(
        self,
        callback: CallbackType | None = None,
        callback_args: CallbackArgs = None,
        switches: SwitchesArg = None,
        timeout: float | None = None,
        exe_log: bool = True,
        measure: str | None = None,
    ) -> None:
        """Run the fast worst-case analysis.

        Returns a named tuple with the nominal measurement, the minimum measurement,
        the component values that yield the maximum measurement, the maximum
        measurement, and the component values that yield the minimum measurement.
        """
        if measure is None:
            raise ValueError("The measure argument must be defined")

        self.last_summary = None
        self.clear_simulation_data()
        self.elements_analysed.clear()
        worst_case_elements: dict[
            str, tuple[float, ComponentDeviation, Literal["component", "parameter"]]
        ] = {}

        def _to_float(value: float | int | str) -> float:
            if isinstance(value, int | float):
                return float(value)
            stripped = value.strip()
            return float(stripped)

        def _coerce_measure(raw: object) -> float:
            if isinstance(raw, int | float):
                return float(raw)
            if isinstance(raw, complex):
                return float(abs(raw))
            if isinstance(raw, str):
                return float(raw.strip())
            if raw is None:
                raise TypeError("Measurement value is None")
            if isinstance(raw, list):
                raise TypeError(
                    "Measurement value is a list; fast worst-case expects a scalar"
                )
            raise TypeError(f"Unsupported measurement type: {type(raw)!r}")

        def check_and_add_component(ref1: str) -> None:
            value_raw, deviation = self.get_component_value_deviation_type(ref1)
            if deviation.min_val == deviation.max_val or deviation.typ == DeviationType.none:
                return
            try:
                numeric_value = _to_float(value_raw)
            except (TypeError, ValueError):
                _logger.debug(
                    "Skipping non-numeric component %s for fast worst-case analysis",
                    ref1,
                )
                return
            worst_case_elements[ref1] = numeric_value, deviation, "component"
            self.elements_analysed.append(ref1)

        def value_change(
            val: float, deviation: ComponentDeviation, target: WorstCaseType
        ) -> float:
            if deviation.typ == DeviationType.tolerance:
                if target == WorstCaseType.max:
                    return val * (1 + deviation.max_val)
                if target == WorstCaseType.min:
                    return val * (1 - deviation.max_val)
                return val
            if deviation.typ == DeviationType.minmax:
                if target == WorstCaseType.max:
                    return deviation.max_val
                if target == WorstCaseType.min:
                    return deviation.min_val
                return val
            _logger.warning("Unknown deviation type for %s", deviation)
            return val

        def set_reference(ref: str, target: WorstCaseType) -> None:
            val, deviation, entry_type = worst_case_elements[ref]
            new_val = value_change(val, deviation, target)
            if entry_type == "component":
                self.editor.set_component_value(ref, new_val)
            elif entry_type == "parameter":
                self.editor.set_parameter(ref, new_val)
            else:
                _logger.warning("Unknown entry type %s", entry_type)

        def extract_measure(data: LogfileData, run_index: int) -> float:
            result = data.get_measure_value(measure, run_index)
            return _coerce_measure(result)

        def run_and_get_measure() -> float:
            run_task = self.run(
                wait_resource=True,
                callback=callback,
                callback_args=callback_args,
                switches=switches,
                timeout=timeout,
                exe_log=exe_log,
            )
            self.wait_completion()
            if run_task is None:
                raise RuntimeError("Simulation did not start; no RunTask returned")
            log_data = self.add_log(run_task)
            if log_data is None:
                raise RuntimeError("Simulation failed; no log data produced")
            result = log_data.get_measure_value(measure)
            return _coerce_measure(result)

        for ref in self.device_deviations:
            check_and_add_component(ref)

        for ref in self.parameter_deviations:
            value_raw, deviation = self.get_parameter_value_deviation_type(ref)
            if deviation.typ not in (DeviationType.tolerance, DeviationType.minmax):
                continue
            try:
                numeric_value = _to_float(value_raw)
            except (TypeError, ValueError):
                _logger.debug(
                    "Skipping non-numeric parameter %s for fast worst-case analysis",
                    ref,
                )
                continue
            worst_case_elements[ref] = numeric_value, deviation, "parameter"
            self.elements_analysed.append(ref)

        for prefix in self.default_tolerance:
            for ref in self.get_components(prefix):
                if ref not in self.device_deviations:
                    check_and_add_component(ref)

        _logger.info(
            "Worst Case Analysis: %d elements to be analysed",
            len(self.elements_analysed),
        )

        self._reset_netlist()
        self.play_instructions()
        self.run(
            wait_resource=True,
            callback=callback,
            callback_args=callback_args,
            switches=switches,
            timeout=timeout,
            exe_log=exe_log,
        )

        for ref in self.elements_analysed:
            set_reference(ref, WorstCaseType.max)
            self.run(
                wait_resource=True,
                callback=callback,
                callback_args=callback_args,
                switches=switches,
                timeout=timeout,
                exe_log=exe_log,
            )
        self.wait_completion()
        self.analysis_executed = True
        self.testbench_executed = True

        log_data = self.read_logfiles()
        nominal = extract_measure(log_data, 0)
        _logger.info("Nominal value: %g", nominal)

        component_deltas: dict[str, float] = {}
        idx = 1
        new_measure = nominal
        last_measure = nominal
        for ref in self.elements_analysed:
            new_measure = extract_measure(log_data, idx)
            component_deltas[ref] = new_measure - last_measure
            last_measure = new_measure
            _logger.info("Component %s: %g", ref, component_deltas[ref])
            idx += 1

        max_setting = {ref: delta > 0 for ref, delta in component_deltas.items()}
        component_changed = False
        for ref, is_positive in max_setting.items():
            if not is_positive:
                set_reference(ref, WorstCaseType.min)
                component_changed = True

        if component_changed:
            max_value = run_and_get_measure()
            idx += 1
        else:
            max_value = new_measure

        iterator = iter(self.elements_analysed)
        while True:
            try:
                ref = next(iterator)
            except StopIteration:
                break
            target = WorstCaseType.min if max_setting[ref] else WorstCaseType.max
            set_reference(ref, target)
            new_value = run_and_get_measure()
            idx += 1
            if new_value > max_value:
                max_setting[ref] = not max_setting[ref]
                max_value = new_value
                iterator = iter(self.elements_analysed)
            set_reference(
                ref, WorstCaseType.max if max_setting[ref] else WorstCaseType.min
            )

        min_setting = {ref: not is_positive for ref, is_positive in max_setting.items()}
        for ref, use_max in min_setting.items():
            set_reference(ref, WorstCaseType.max if use_max else WorstCaseType.min)

        min_value = run_and_get_measure()
        idx += 1

        iterator = iter(self.elements_analysed)
        while True:
            try:
                ref = next(iterator)
            except StopIteration:
                break
            target = WorstCaseType.min if min_setting[ref] else WorstCaseType.max
            set_reference(ref, target)
            new_value = run_and_get_measure()
            idx += 1
            if new_value < min_value:
                min_setting[ref] = not min_setting[ref]
                min_value = new_value
                iterator = iter(self.elements_analysed)
            set_reference(
                ref, WorstCaseType.max if min_setting[ref] else WorstCaseType.min
            )

        min_comp_values: dict[str, float] = {}
        max_comp_values: dict[str, float] = {}
        for ref in self.elements_analysed:
            value, deviation, _kind = worst_case_elements[ref]
            min_comp_values[ref] = value_change(
                value, deviation, WorstCaseType.max if min_setting[ref] else WorstCaseType.min
            )
            max_comp_values[ref] = value_change(
                value, deviation, WorstCaseType.max if max_setting[ref] else WorstCaseType.min
            )

        self.clear_simulation_data()
        self.cleanup_files()
        self._reset_netlist()
        self.play_instructions()

        summary = WorstCaseSummary(
            nominal,
            min_value,
            max_comp_values,
            max_value,
            min_comp_values,
        )
        self.simulation_results["fast_worst_case"] = summary
        self.last_summary: WorstCaseSummary | None = summary
        return None
