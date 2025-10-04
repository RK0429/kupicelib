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
# Name:        failure_modes.py
# Purpose:     Class to automate FMEA
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     10-08-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
from typing import Any

from ...editor.base_editor import BaseEditor, ComponentNotFoundError
from ...editor.spice_editor import SpiceEditor
from ..sim_runner import RunTask, SimRunner
from ..simulator import Simulator
from .sim_analysis import AnyRunner, SimAnalysis


class FailureMode(SimAnalysis):
    """This Class will replace each component on the circuit for their failure modes and
    launch a simulation.

    The following failure modes are built-in:

    * Resistors, Capacitors, Inductors and Diodes     # Open Circuit     # Short Circuit

    * Transistors     # Open Circuit (All pins)     # Short Circuit (All pins)     #
    Short Circuit Base-Emitter (Bipolar) / Gate-Source (MOS)     # Short Circuit
    Collector-Emitter (Bipolar) / Drain-Source (MOS)

    * Integrated Circuits     # The failure modes are defined by the user by using the
    add_failure_mode() method
    """

    def __init__(
        self,
        circuit_file: str | BaseEditor,
        simulator: type[Simulator] | None = None,
        runner: AnyRunner | None = None,
    ) -> None:
        super().__init__(circuit_file, runner)
        self.simulator = simulator
        if not isinstance(self.editor, SpiceEditor):
            raise TypeError("FailureMode requires a SpiceEditor editor instance")
        self._spice_editor: SpiceEditor = self.editor
        if simulator is not None and isinstance(self.runner, SimRunner):
            self.runner.set_simulator(simulator)
        editor = self._spice_editor
        self.resistors: list[str] = editor.get_components("R")
        self.capacitors: list[str] = editor.get_components("C")
        self.inductors: list[str] = editor.get_components("L")
        self.diodes: list[str] = editor.get_components("D")
        self.bipolars: list[str] = editor.get_components("Q")
        self.mosfets: list[str] = editor.get_components("M")
        self.subcircuits: list[str] = editor.get_components("X")
        self.user_failure_modes: dict[str, dict[str, Any]] = OrderedDict()
        self.results: dict[str, RunTask | None] = {}

    def add_failure_circuit(self, component: str, sub_circuit: str) -> None:
        if not component.startswith("X"):
            raise RuntimeError(
                "The failure modes addition only works with sub circuits"
            )
        if component not in self.subcircuits:
            raise ComponentNotFoundError()
        raise NotImplementedError("TODO")  # TODO: Implement this

    def add_failure_mode(
        self,
        component: str,
        short_pins: Iterable[str],
        open_pins: Iterable[str],
    ) -> None:
        if not component.startswith("X"):
            raise RuntimeError("The failure modes addition only works with subcircuits")
        if component not in self.subcircuits:
            raise ComponentNotFoundError()
        raise NotImplementedError("TODO")  # TODO: Implement this

    def run_all(self) -> dict[str, RunTask | None]:
        """Execute all predefined failure modes for two-pin components.

        The current implementation focuses on basic modes (open and short) for
        resistors, capacitors, inductors, and diodes. The collected results are stored
        in ``self.results`` keyed by ``"<reference>_<mode>"``.
        """

        self.results.clear()

        for resistor in self.resistors:
            self.editor.set_component_value(resistor, "1f")
            short_result = self.runner.run(self.editor)
            self.simulations.append(short_result)
            self.results[f"{resistor}_S"] = short_result

            self.editor.remove_component(resistor)
            open_result = self.runner.run(self.editor)
            self.simulations.append(open_result)
            self.results[f"{resistor}_O"] = open_result
            self.editor.reset_netlist()

        for two_pin_components in (self.capacitors, self.inductors, self.diodes):
            for component in two_pin_components:
                component_info = self.editor.get_component(component)
                self.editor.remove_component(component)
                open_result = self.runner.run(self.editor)
                self.simulations.append(open_result)
                self.results[f"{component}_O"] = open_result

                nodes = " ".join(component_info.ports)
                replacement_line = f"Rfmea_short_{component} {nodes} 1f"
                netlist = self._spice_editor.netlist
                line_index = netlist.index(component_info.line)
                netlist[line_index] = replacement_line
                short_result = self.runner.run(self.editor)
                self.simulations.append(short_result)
                self.results[f"{component}_S"] = short_result
                self.editor.reset_netlist()

        return self.results.copy()
