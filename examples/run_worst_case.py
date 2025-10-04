# -- Start of Example 1 --
import logging
from typing import Any, cast

import kupicelib
from kupicelib import (  # Imports the class that manipulates the asc file
    AscEditor,
    SimRunner,
)
from kupicelib.sim.tookit.worst_case import WorstCaseAnalysis
from kupicelib.simulators.ltspice_simulator import LTspice

kupicelib.set_log_level(logging.INFO)


sallenkey = AscEditor("./testfiles/sallenkey.asc")  # Reads the asc file into memory
runner = SimRunner(
    simulator=LTspice, output_folder="./temp_wca", verbose=True
)  # Instantiates the runner with a temp folder set
wca = WorstCaseAnalysis(
    cast(Any, sallenkey), cast(Any, runner)
)  # Instantiates the Worst Case Analysis class

# The following lines set the default tolerances for the components
wca.set_tolerance("R", 0.01)  # 1% tolerance
wca.set_tolerance("C", 0.1)  # 10% tolerance
# wca.set_tolerance('V', 0.1)  # 10% tolerance. For Worst Case analysis,
# the distribution is irrelevant
wca.set_tolerance(
    "I", 0.1
)  # 10% tolerance. For Worst Case analysis, the distribution is irrelevant
# Some components can have a different tolerance
wca.set_tolerance(
    "R1", 0.05
)  # 5% tolerance for R1 only. This only overrides the default tolerance for R1
wca.set_tolerance(
    "R4", 0.0
)  # 5% tolerance for R1 only. This only overrides the default tolerance for R1

# Tolerances can be set for parameters as well.
wca.set_parameter_deviation("Vos", 3e-4, 5e-3)

# Finally the netlist is saved to a file
wca.save_netlist("./testfiles/sallenkey_wc.asc")
# -- End of Example 1 --

wca.run_testbench()  # Runs the simulation with splits of 100 runs each

logs = (
    wca.read_logfiles()
)  # Reads the log files and stores the results in the results attribute
logs.export_data("./temp_wca/data.csv")  # Exports the data to a csv file

print("Worst case results:")
for param in ("fcut", "fcut_FROM"):
    print(
        f"{param}: min:{logs.min_measure_value(param)} max:{logs.max_measure_value(param)}"
    )

# All components sensitivity
sens = wca.make_sensitivity_analysis("fcut", "*")
if not isinstance(sens, dict):
    raise RuntimeError("Sensitivity analysis did not return component data")
for comp, (mean_pct, sigma_pct) in sens.items():
    print(f"{comp}: Mean: {mean_pct:.2f}% StdDev:{sigma_pct:.2f}%")
input("Press Enter")

wca.cleanup_files()  # Deletes the temporary files

print("=====================================")
# Now using the second method, where the simulations are ran one by one
wca.clear_simulation_data()  # Clears the simulation data
wca.reset_netlist()  # Resets the netlist to the original
wca.run_analysis()  # Makes the Worst Case Analysis
min_max = wca.get_min_max_measure_value("fcut")
if min_max is None:
    raise RuntimeError("Missing measurement results for fcut")
min_fcut, max_fcut = min_max
print(f"fcut: min:{min_fcut} max:{max_fcut}")
sens_r1 = wca.make_sensitivity_analysis("fcut", "R1")
if not isinstance(sens_r1, tuple):
    raise RuntimeError("Sensitivity analysis for R1 did not return tuple data")
print(f"R1: Mean: {sens_r1[0]:.2f}% StdDev:{sens_r1[1]:.2f}%")
input("Press Enter")

# All components sensitivity
sens = wca.make_sensitivity_analysis("fcut", "*")
if not isinstance(sens, dict):
    raise RuntimeError("Sensitivity analysis did not return component data")
for comp, (mean_pct, sigma_pct) in sens.items():
    print(f"{comp}: Mean: {mean_pct:.2f}% StdDev:{sigma_pct:.2f}%")
input("Press Enter")
wca.cleanup_files()  # Deletes the temporary files
