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
# Name:        test_kupicelib.py
# Purpose:     Tool used to launch Spice simulation in batch mode. Netlsts can
#              be updated by user instructions
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
"""@author:        Nuno Brum.

@copyright:     Copyright 2022 @credits:       nunobrum

@license:       GPLv3 @maintainer:    Nuno Brum @email:         me@nunobrum.com

@

file:
test_kupicelib.py
@date:          2022-09-19

@note           kupicelib ltsteps + sim_commander + raw_read unit test
run ./test/unittests/test_kupicelib
"""

import math  # numerical helpers
import os  # platform independent paths

# ------------------------------------------------------------------------------
# Python Libs
import sys  # python path handling
import unittest  # performs test
from pathlib import Path
from typing import Any, cast

from kupicelib.editor.spice_editor import SpiceEditor
from kupicelib.log.logfile_data import LTComplex
from kupicelib.log.ltsteps import LTSpiceLogReader
from kupicelib.raw.raw_read import RawRead
from kupicelib.sim.sim_runner import SimRunner

#
# Module libs

sys.path.append(
    os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + "/../")
)  # add project root to lib search path


def has_ltspice_detect():
    from kupicelib.simulators.ltspice_simulator import LTspice

    global ltspice_simulator
    ltspice_simulator = LTspice
    # return False
    return ltspice_simulator.is_available()


# ------------------------------------------------------------------------------
has_ltspice = has_ltspice_detect()
skip_ltspice_tests = not has_ltspice
print("skip_ltspice_tests", skip_ltspice_tests)
hide_exe_print_statements = True  # set to False if you want Spice to log to console
# ------------------------------------------------------------------------------
if os.path.abspath(os.curdir).endswith("unittests"):
    test_dir = "../examples/testfiles/"
    temp_dir = "../examples/testfiles/temp/"
else:
    test_dir = "./examples/testfiles/"
    temp_dir = "./examples/testfiles/temp/"

print("test_dir", test_dir)
# ------------------------------------------------------------------------------


class test_kupicelib(unittest.TestCase):
    """Unnittesting kupicelib."""

    # *****************************
    @unittest.skipIf(skip_ltspice_tests, "Skip if not in windows environment")
    def test_batch_test(self):
        """@note   inits class."""
        print("Starting test_batch_test")
        from kupicelib.simulators.ltspice_simulator import LTspice

        # prepare
        self.sim_files: list[tuple[Path, Path]] = []
        self.measures: dict[str, object] = {}

        def processing_data(raw_file: Path, log_file: Path) -> None:
            print(
                f"Handling the simulation data of {raw_file}, log file {log_file}"
            )
            self.sim_files.append((raw_file, log_file))

        # select spice model
        LTspice.create_netlist(
            test_dir + "Batch_Test.asc", exe_log=hide_exe_print_statements
        )
        editor = SpiceEditor(test_dir + "Batch_Test.net")
        runner = SimRunner(parallel_sims=4, output_folder="./output", simulator=LTspice)
        runner_any = cast(Any, runner)
        editor.set_parameters(res=0, cap=100e-6)
        editor.set_component_value("R2", "2k")  # Modifying the value of a resistor
        editor.set_component_value("R1", "4k")
        editor.set_element_model("V3", "SINE(0 1 3k 0 0 0)")  # Modifying the
        editor.set_component_value(
            "XU1:C2", 20e-12
        )  # modifying a cap inside a component
        # define simulation
        editor.add_instructions(
            "; Simulation settings",
            # ".step dec param freq 10k 1Meg 10",
        )
        editor.set_parameter("run", "0")

        for opamp in (
            "AD712",
            "AD820_XU1",
        ):  # don't use AD820, it is defined in the file and will mess up newer LTspice versions
            editor.set_element_model("XU1", opamp)
            for supply_voltage in (5, 10, 15):
                editor.set_component_value("V1", supply_voltage)
                editor.set_component_value("V2", -supply_voltage)
                # overriding the automatic netlist naming
                run_netlist_file = f"{editor.circuit_file.name}_{opamp}_{supply_voltage}.net"
                runner_any.run(
                    editor,
                    run_filename=run_netlist_file,
                    callback=processing_data,
                    exe_log=hide_exe_print_statements,
                )

        runner.wait_completion()
        for task in runner.completed_tasks:
            task_any = cast(Any, task)
            netlist_path = task_any.netlist_file
            raw_path = task_any.raw_file
            log_path = task_any.log_file
            self.assertIsNotNone(raw_path, "Raw path missing")
            self.assertIsNotNone(log_path, "Log path missing")
            assert raw_path is not None
            assert log_path is not None
            self.assertTrue(netlist_path.exists(), "Created the netlist")
            self.assertTrue(raw_path.exists(), "Created the raw file")
            self.assertTrue(log_path.exists(), "Created the log file")
        runner.cleanup_files()
        for task in runner.completed_tasks:
            task_any = cast(Any, task)
            netlist_path = task_any.netlist_file
            raw_path = task_any.raw_file
            log_path = task_any.log_file
            if netlist_path is not None:
                self.assertFalse(netlist_path.exists(), "Deleted the netlist")
            if raw_path is not None:
                self.assertFalse(raw_path.exists(), "Deleted the raw file")
            if log_path is not None:
                self.assertFalse(log_path.exists(), "Deleted the log file")

        # Sim Statistics
        print(
            "Successful/Total Simulations: "
            + str(runner.okSim)
            + "/"
            + str(runner.runno)
        )
        self.assertEqual(runner.okSim, 6)
        self.assertEqual(runner.runno, 6)

        # check
        editor.reset_netlist()
        # this is needed with the newer LTspice versions, as AD820 has been
        # defined in the file and in a lib
        editor.set_element_model("XU1", "AD712")
        editor.remove_instruction(
            ".meas TRAN period FIND time WHEN V(out)=0 RISE=1"
        )  # not in TRAN now
        editor.remove_instruction(
            ".meas Vout1m FIND V(OUT) AT 1m"
        )  # old style, not working on AC with these frequencies

        editor.set_element_model("V3", "AC 1 0")
        editor.add_instructions(
            "; Simulation settings",
            ".ac dec 30 1 10Meg",
            ".meas AC GainAC MAX mag(V(out)) ; find the peak response and call it "
            "Gain"
            "",
            ".meas AC FcutAC TRIG mag(V(out))=GainAC/sqrt(2) FALL=last",
            ".meas AC Vout1m FIND V(out) AT 1Hz",
        )

        raw_file, log_file = runner_any.run_now(
            editor, run_filename="no_callback.net", exe_log=hide_exe_print_statements
        )
        if raw_file is None or log_file is None:
            self.fail("Runner did not return output files")
        print("no_callback", raw_file, log_file)
        log = LTSpiceLogReader(str(log_file))
        for measure in log.get_measure_names():
            print(measure, "=", log.get_measure_value(measure))
        vout1m = cast(LTComplex, log.get_measure_value("vout1m"))
        print("vout1m.mag_db=", vout1m.mag_db())
        print("vout1m.ph=", vout1m.ph)

        fcutac = cast(float, log.get_measure_value("fcutac"))
        self.assertAlmostEqual(
            fcutac, 6.3e06, delta=0.1e6
        )  # have to be imprecise, different ltspice versions give different replies
        # self.assertEqual(log.get_measure_value('vout1m'), 1.9999977173843142 -
        # 1.8777417486008045e-09j)  # excluded, diffifult to make compatible
        self.assertAlmostEqual(
            vout1m.mag_db(), 6.0206, delta=0.0001
        )
        self.assertAlmostEqual(
            vout1m.ph, -1.7676e-05, delta=0.0001e-05
        )

    @unittest.skipIf(skip_ltspice_tests, "Skip if not in windows environment")
    def test_run_from_spice_editor(self):
        """Run command on SpiceEditor."""
        print("Starting test_run_from_spice_editor")
        runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
        runner_any = cast(Any, runner)
        # select spice model
        netlist = SpiceEditor(test_dir + "testfile.net")
        # set default arguments
        netlist.set_parameters(res=0.001, cap=100e-6)
        # define simulation
        netlist.add_instructions(
            "; Simulation settings",
            # [".STEP PARAM Rmotor LIST 21 28"],
            ".TRAN 3m",
            # ".step param run 1 2 1"
        )
        # do parameter sweep
        for res in range(5):
            # runner.runs_to_do = range(2)
            netlist.set_parameters(ANA=res)
            task = runner_any.run(netlist, exe_log=hide_exe_print_statements)
            self.assertIsNotNone(task, "SimRunner.run returned None")
            if task is None:
                continue
            result = task.wait_results()
            if not isinstance(result, tuple):
                continue
            raw_obj, log_obj = cast(tuple[object, object], result)
            if not isinstance(raw_obj, str | Path) or not isinstance(
                log_obj, str | Path
            ):
                continue
            raw, log = raw_obj, log_obj
            print(f"Raw file '{raw}' | Log File '{log}'")
        runner.wait_completion()
        # Sim Statistics
        print(
            "Successful/Total Simulations: "
            + str(runner.okSim)
            + "/"
            + str(runner.runno)
        )
        self.assertEqual(runner.okSim, 5)
        self.assertEqual(runner.runno, 5)

    @unittest.skipIf(skip_ltspice_tests, "Skip if not in windows environment")
    def test_sim_runner(self):
        """SimRunner and SpiceEditor singletons."""
        print("Starting test_sim_runner")
        # Old legacy class that merged SpiceEditor and SimRunner

        def callback_function(raw_file: Path, log_file: Path) -> None:
            print(
                f"Handling the simulation data of {raw_file}, log file {log_file}"
            )

        # Force single-run execution so the bias file exists before the next
        # simulation starts. Alternatively call wait_completion() after each
        # run or execute run_now and trigger the callback manually.
        runner = SimRunner(
            output_folder=temp_dir, simulator=ltspice_simulator, parallel_sims=1
        )
        runner_any = cast(Any, runner)
        # select spice model
        SE = SpiceEditor(test_dir + "testfile.net")
        tstart = 0
        bias_file = ""
        for tstop in (2, 5, 8, 10):
            SE.reset_netlist()  # Reset the netlist to the original status
            tduration = tstop - tstart
            SE.add_instruction(
                f".tran {tduration}",
            )
            if tstart != 0:
                SE.add_instruction(f".loadbias {bias_file}")
                # Put here your parameter modifications
                # runner.set_parameters(param1=1, param2=2, param3=3)
            bias_file = f"sim_loadbias_{tstop}.txt"
            SE.add_instruction(
                f".savebias {bias_file} internal time={tduration}"
            )
            tstart = tstop
            runner_any.run(
                SE, callback=callback_function, exe_log=hide_exe_print_statements
            )

        SE.reset_netlist()
        SE.add_instruction(".ac dec 40 1m 1G")
        SE.set_component_value("V1", "AC 1 0")
        runner_any.run(SE, callback=callback_function, exe_log=hide_exe_print_statements)
        runner.wait_completion()

        # Sim Statistics
        print(
            "Successful/Total Simulations: "
            + str(runner.okSim)
            + "/"
            + str(runner.runno)
        )
        self.assertEqual(runner.okSim, 5)
        self.assertEqual(runner.runno, 5)

    @unittest.skipIf(False, "Execute All")
    def test_ltsteps_measures(self):
        """LTSpiceLogReader Measures from Batch_Test.asc."""
        print("Starting test_ltsteps_measures")
        assert_data = {
            "vout1m": [
                -0.0186257,
                -1.04378,
                -1.64283,
                -0.622014,
                1.32386,
                -1.35125,
                -1.88222,
                1.28677,
                1.03154,
                0.953548,
                -0.192821,
                -1.42535,
                0.451607,
                0.0980979,
                1.55525,
                1.66809,
                0.11246,
                0.424023,
                -1.30035,
                0.614292,
                -0.878185,
            ],
            "vin_rms": [
                0.706221,
                0.704738,
                0.708225,
                0.707042,
                0.704691,
                0.704335,
                0.704881,
                0.703097,
                0.70322,
                0.703915,
                0.703637,
                0.703558,
                0.703011,
                0.702924,
                0.702944,
                0.704121,
                0.704544,
                0.704193,
                0.704236,
                0.703701,
                0.703436,
            ],
            "vout_rms": [
                1.41109,
                1.40729,
                1.41292,
                1.40893,
                1.40159,
                1.39763,
                1.39435,
                1.38746,
                1.38807,
                1.38933,
                1.38759,
                1.38376,
                1.37771,
                1.37079,
                1.35798,
                1.33252,
                1.24314,
                1.07237,
                0.875919,
                0.703003,
                0.557131,
            ],
            "gain": [
                1.99809,
                1.99689,
                1.99502,
                1.99271,
                1.98894,
                1.98432,
                1.97814,
                1.97336,
                1.97387,
                1.97372,
                1.97202,
                1.9668,
                1.95973,
                1.95012,
                1.93184,
                1.89246,
                1.76445,
                1.52284,
                1.24379,
                0.999007,
                0.792014,
            ],
            "period": [
                0.000100148,
                7.95811e-005,
                6.32441e-005,
                5.02673e-005,
                3.99594e-005,
                3.1772e-005,
                2.52675e-005,
                2.01009e-005,
                1.59975e-005,
                1.27418e-005,
                1.01541e-005,
                8.10036e-006,
                6.47112e-006,
                5.18241e-006,
                4.16639e-006,
                3.37003e-006,
                2.75114e-006,
                2.26233e-006,
                1.85367e-006,
                1.50318e-006,
                1.20858e-006,
            ],
            "period_at": [
                0.000100148,
                7.95811e-005,
                6.32441e-005,
                5.02673e-005,
                3.99594e-005,
                3.1772e-005,
                2.52675e-005,
                2.01009e-005,
                1.59975e-005,
                1.27418e-005,
                1.01541e-005,
                8.10036e-006,
                6.47112e-006,
                5.18241e-006,
                4.16639e-006,
                3.37003e-006,
                2.75114e-006,
                2.26233e-006,
                1.85367e-006,
                1.50318e-006,
                1.20858e-006,
            ],
        }
        if has_ltspice:
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            runner_any = cast(Any, runner)
            raw_file, log_file = runner_any.run_now(
                test_dir + "Batch_Test_Simple.asc", exe_log=hide_exe_print_statements
            )
            print(raw_file, log_file)
            self.assertIsNotNone(raw_file, "Batch_Test_Simple.asc run failed")
            self.assertIsNotNone(log_file, "Batch_Test_Simple.asc log missing")
            assert raw_file is not None
            assert log_file is not None
            log_path = log_file
        else:
            log_path = Path(test_dir + "Batch_Test_Simple_1.log")
        log = LTSpiceLogReader(str(log_path))

        self.assertEqual(log.step_count, 21, "Batch_Test_Simple step_count is wrong")
        # raw = RawRead(raw_file)
        for measure in assert_data:
            print("measure", measure)
            for step in range(log.step_count):
                actual = cast(float, log.get_measure_value(measure, step))
                print(actual, assert_data[measure][step])
                self.assertAlmostEqual(
                    actual,
                    assert_data[measure][step],
                    places=1,
                )  # TODO the reference data should be adapted, is too imprecise

    @unittest.skipIf(False, "Execute All")
    def test_operating_point(self):
        """Operating Point Simulation Test."""
        print("Starting test_operating_point")
        if has_ltspice:
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            runner_any = cast(Any, runner)
            raw_file, _log_file = runner_any.run_now(
                test_dir + "DC op point.asc", exe_log=hide_exe_print_statements
            )
            self.assertIsNotNone(raw_file, "DC op point run failed")
            assert raw_file is not None
        else:
            raw_file = test_dir + "DC op point_1.raw"
            # log_file = test_dir + "DC op point_1.log"
        raw = RawRead(str(raw_file))
        traces = [raw.get_trace(trace)[0] for trace in sorted(raw.get_trace_names())]
        self.assertListEqual(
            traces,
            [
                4.999999873689376e-05,
                4.999999873689376e-05,
                -4.999999873689376e-05,
                1.0,
                0.5,
            ],
            "Lists are different",
        )

    @unittest.skipIf(False, "Execute All")
    def test_operating_point_step(self):
        """Operating Point Simulation with Steps."""
        print("Starting test_operating_point_step")
        if has_ltspice:
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            runner_any = cast(Any, runner)
            raw_file, _log_file = runner_any.run_now(
                test_dir + "DC op point - STEP.asc", exe_log=hide_exe_print_statements
            )
            self.assertIsNotNone(raw_file, "DC op point - STEP run failed")
            assert raw_file is not None
        else:
            raw_file = test_dir + "DC op point - STEP_1.raw"
        raw = RawRead(raw_file)
        vin = raw.get_trace("V(in)")

        for i, b in enumerate(
            ("V(in)", "V(b4)", "V(b3)", "V(b2)", "V(b1)", "V(out)"),
        ):
            meas = raw.get_trace(b)
            for step in range(raw.nPoints):
                self.assertEqual(meas[step], vin[step] * 2**-i)

    @unittest.skipIf(False, "Execute All")
    def test_transient(self):
        """Transient Simulation test."""
        print("Starting test_transient")
        if has_ltspice:
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            runner_any = cast(Any, runner)
            raw_file, log_file = runner_any.run_now(
                test_dir + "TRAN.asc", exe_log=hide_exe_print_statements
            )
            self.assertIsNotNone(raw_file, "TRAN run failed")
            self.assertIsNotNone(log_file, "TRAN log missing")
            assert raw_file is not None
            assert log_file is not None
            raw_path = raw_file
            log_path = log_file
        else:
            raw_path = Path(test_dir + "TRAN_1.raw")
            log_path = Path(test_dir + "TRAN_1.log")
        raw = RawRead(str(raw_path))
        log = LTSpiceLogReader(str(log_path))
        vout = raw.get_trace("V(out)")
        meas = (
            "t1",
            "t2",
            "t3",
            "t4",
            "t5",
        )
        time = (
            1e-3,
            2e-3,
            3e-3,
            4e-3,
            5e-3,
        )
        for m, t in zip(meas, time, strict=False):
            log_value = cast(float, log.get_measure_value(m))
            raw_value = cast(float, vout.get_point_at(t))
            print(log_value, raw_value, log_value - raw_value)
            self.assertAlmostEqual(
                log_value, raw_value, 2, "Mismatch between log file and raw file"
            )

    @unittest.skipIf(False, "Execute All")
    def test_transient_steps(self):
        """Transient simulation with stepped data."""
        print("Starting test_transient_steps")
        if has_ltspice:
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            runner_any = cast(Any, runner)
            raw_file, log_file = runner_any.run_now(
                test_dir + "TRAN - STEP.asc", exe_log=hide_exe_print_statements
            )
            self.assertIsNotNone(raw_file, "TRAN - STEP run failed")
            self.assertIsNotNone(log_file, "TRAN - STEP log missing")
            assert raw_file is not None
            assert log_file is not None
            raw_path = raw_file
            log_path = log_file
        else:
            raw_path = Path(test_dir + "TRAN - STEP_1.raw")
            log_path = Path(test_dir + "TRAN - STEP_1.log")

        raw = RawRead(str(raw_path))
        log = LTSpiceLogReader(str(log_path))
        vout = raw.get_trace("V(out)")
        meas = (
            "t1",
            "t2",
            "t3",
            "t4",
            "t5",
        )
        time = (
            1e-3,
            2e-3,
            3e-3,
            4e-3,
            5e-3,
        )
        for m, t in zip(meas, time, strict=False):
            print(m)
            for step, step_dict in enumerate(raw.steps or []):
                log_value = cast(float, log.get_measure_value(m, step))
                raw_value = cast(float, vout.get_point_at(t, step))
                print(step, step_dict, log_value, raw_value, log_value - raw_value)
                self.assertAlmostEqual(
                    log_value,
                    raw_value,
                    2,
                    f"Mismatch between log file and raw file in step :{step_dict} measure: {m} ",
                )

    @unittest.skipIf(False, "Execute All")
    def test_ac_analysis(self):
        """AC Analysis Test."""

        def checkresults(raw_file: str | Path, res_value: float, cap_value: float) -> None:
            # Compute the RC AC response with the resistor and capacitor values from
            # the netlist.
            raw = RawRead(raw_file)
            vout_trace = raw.get_trace("V(out)")
            vin_trace = raw.get_trace("V(in)")
            axis_trace = raw.axis
            if axis_trace is None:
                self.fail("Raw data missing axis information")
            for point, freq in enumerate(axis_trace):
                vout1 = vout_trace.get_point_at(freq)
                vout2 = vout_trace.get_point(point)
                vin = vin_trace.get_point(point)
                self.assertEqual(vout1, vout2)
                self.assertEqual(abs(vin), 1)
                # Calculate the magnitude of the answer Vout = Vin/(1+jwRC)
                h = vin / (1 + 2j * math.pi * freq * res_value * cap_value)
                self.assertAlmostEqual(
                    abs(vout1),
                    abs(h),
                    places=5,
                    msg=(
                        f"{raw_file}: Difference between theoretical value and "
                        f"simulation at point {point}"
                    ),
                )
                vout_phase = math.atan2(vout1.imag, vout1.real)
                h_phase = math.atan2(h.imag, h.real)
                self.assertAlmostEqual(
                    vout_phase,
                    h_phase,
                    places=5,
                    msg=(
                        f"{raw_file}: Difference between theoretical value and "
                        f"simulation at point {point}"
                    ),
                )

        print("Starting test_ac_analysis")

        if has_ltspice:
            from kupicelib.editor.asc_editor import AscEditor

            editor = AscEditor(test_dir + "AC.asc")
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            runner_any = cast(Any, runner)
            raw_file, _log_file = runner_any.run_now(
                editor, exe_log=hide_exe_print_statements
            )
            self.assertIsNotNone(raw_file, "AC analysis run failed")
            assert raw_file is not None

            res_value = editor.get_component_floatvalue("R1")
            cap_value = editor.get_component_floatvalue("C1")
        else:
            raw_file = test_dir + "AC_1.raw"
            # log_file = test_dir + "AC_1.log"
            res_value = 100
            cap_value = 10e-6
        checkresults(raw_file, res_value, cap_value)

        raw_file = test_dir + "AC_1.ascii.raw"
        checkresults(raw_file, 100, 10e-6)

    @unittest.skipIf(False, "Execute All")
    def test_ac_analysis_steps(self):
        """AC Analysis Test with steps."""
        print("Starting test_ac_analysis_steps")

        if has_ltspice:
            from kupicelib.editor.asc_editor import AscEditor

            editor = AscEditor(test_dir + "AC - STEP.asc")
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            runner_any = cast(Any, runner)
            raw_file, _log_file = runner_any.run_now(
                editor, exe_log=hide_exe_print_statements
            )
            self.assertIsNotNone(raw_file, "AC - STEP run failed")
            assert raw_file is not None
            cap_value = editor.get_component_floatvalue("C1")
            raw_path = raw_file
        else:
            raw_path = Path(test_dir + "AC - STEP_1.raw")
            # log_file = test_dir + "AC - STEP_1.log"
            cap_value = 159.1549e-6  # 159.1549uF
        # Compute the RC AC response with the resistor and capacitor values from
        # the netlist.
        raw = RawRead(str(raw_path))
        vin_trace = raw.get_trace("V(in)")
        vout_trace = raw.get_trace("V(out)")
        axis_trace = raw.axis
        if axis_trace is None:
            self.fail("Raw data missing axis information")
        for step, step_dict in enumerate(raw.steps or []):
            res_value = cast(float, step_dict["r1"])
            # print(step, step_dict)
            for point in range(0, raw.get_len(step), 10):  # 10 times less points
                print(point, end=" - ")
                vout = vout_trace.get_point(point, step)
                vin = vin_trace.get_point(point, step)
                freq = axis_trace.get_point(point, step)
                # Calculate the magnitude of the answer Vout = Vin/(1+jwRC)
                h = vin / (1 + 2j * math.pi * freq * res_value * cap_value)
                # print(freq, vout, h, vout - h)
                vout_mag = float(abs(vout))
                h_mag = float(abs(h))
                self.assertAlmostEqual(
                    vout_mag,
                    h_mag,
                    5,
                    f"Difference between theoretical value ans simulation at point {point}:",
                )
                angle_vout = math.atan2(vout.imag, vout.real)
                angle_h = math.atan2(h.imag, h.real)
                self.assertAlmostEqual(
                    angle_vout,
                    angle_h,
                    5,
                    f"Difference between theoretical value ans simulation at point {point}",
                )
        print(" end")

    @unittest.skipIf(False, "Execute All")
    def test_fourier_log_read(self):
        """Fourier Analysis Test."""
        print("Starting test_fourier_log_read")
        if has_ltspice:
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            runner_any = cast(Any, runner)
            raw_file, log_file = runner_any.run_now(
                test_dir + "Fourier_30MHz.asc", exe_log=hide_exe_print_statements
            )
            self.assertIsNotNone(raw_file, "Fourier run failed")
            self.assertIsNotNone(log_file, "Fourier log missing")
            assert raw_file is not None
            assert log_file is not None
            raw_path = raw_file
            log_path = log_file
        else:
            raw_path = Path(test_dir + "Fourier_30MHz_1.raw")
            log_path = Path(test_dir + "Fourier_30MHz_1.log")
        raw = RawRead(str(raw_path))
        log = LTSpiceLogReader(str(log_path))
        print(log.fourier)
        axis = raw.axis
        assert axis is not None
        tmax = float(max(axis))
        dc_component = float(raw.get_wave("V(a)").mean())
        fundamental = float(log.fourier["V(a)"][0].fundamental)
        self.assertEqual(fundamental, 30e6, "Fundamental frequency is not 30MHz")
        n_periods_calc = tmax * fundamental
        self.assertAlmostEqual(
            float(log.fourier["V(a)"][0].n_periods),
            n_periods_calc,
            5,
            "Mismatch in calculated number of periods",
        )
        self.assertAlmostEqual(
            float(log.fourier["V(a)"][0].dc_component),
            dc_component,
            2,
            "Mismatch in DC component",
        )
        self.assertEqual(
            len(log.fourier["V(a)"][0].harmonics),
            9,
            "Mismatch in requested number of harmonics",
        )

    #
    # def test_pathlib(self):
    #     """pathlib support"""
    #     import pathlib
    #     DIR = pathlib.Path("../tests")
    #     raw_file = DIR / "AC - STEP_1.raw"
    #     raw = RawRead(raw_file)


# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("Starting tests on kupicelib")
    unittest.main()
    print("Tests completed on kupicelib")
# ------------------------------------------------------------------------------
