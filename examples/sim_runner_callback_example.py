from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from kupicelib.simulators.ltspice_simulator import LTspice

try:
    from rich.logging import RichHandler
except ImportError:
    RichHandler = None

from random import random
from time import sleep

import kupicelib
from kupicelib import SimRunner, SpiceEditor

kupicelib.set_log_level(logging.DEBUG)
if RichHandler is not None:
    kupicelib.add_log_handler(RichHandler())


def processing_data(
    raw_file: Path,
    log_file: Path,
    *,
    supply_voltage: float | int,
    opamp: str,
) -> str:
    print(
        "Handling the simulation data of "
        f"{raw_file}"
        ", log file "
        f"{log_file}"
    )
    print(f"Supply Voltage: {supply_voltage}, OpAmp: {opamp}")
    time_to_sleep: float = random() * 5
    print(f"Sleeping for {time_to_sleep} seconds")
    sleep(time_to_sleep)
    return "This is the result passed to the iterator"


runner = SimRunner(
    simulator=LTspice, output_folder="./temp_batch3"
)  # Configures the simulator to use and output
# folder

netlist = SpiceEditor(
    "./testfiles/Batch_Test.net"
)  # Open the Spice Model, and creates the .net
# set default arguments
netlist.set_parameters(res=0, cap=100e-6)
netlist["R2"].value = "2k"  # Modifying the value of a resistor
netlist["R1"].value = "4k"
netlist["V3"].value_str = (
    "SINE(0 1 3k 0 0 0)"  # Modifying the model of a voltage source
)
netlist.set_component_value("XU1:C2", 20e-12)  # modifying a component in a subcircuit
# define simulation
netlist.add_instructions("; Simulation settings", ";.param run = 0")
netlist.set_parameter("run", 0)

use_run_now = False

for opamp in (
    "AD712",
    "AD820_ALT",
):  # don't use AD820, it is defined in the file and will mess up newer LTspice versions
    netlist["XU1"].model = opamp
    for supply_voltage in (5, 10, 15):
        netlist["V1"].value = supply_voltage
        netlist["V2"].value = -supply_voltage
        # overriding the automatic netlist naming
        run_netlist_file = f"{netlist.netlist_file.stem}_{opamp}_{supply_voltage}.net"
        if use_run_now:
            runner.run_now(netlist, run_filename=run_netlist_file)
        else:
            runner.run(
                netlist,
                run_filename=run_netlist_file,
                callback=processing_data,
                callback_args=(supply_voltage, opamp),
            )

for results in runner:
    print(results)

netlist.reset_netlist()
netlist.remove_Xinstruction(
    r"\.meas TRAN.*"
)  # This is now needed because LTspice no longer supports cross
netlist.add_instructions(  # Adding additional instructions
    "; Simulation settings",
    ".ac dec 30 10 1Meg",
    ".meas AC Gain MAX mag(V(out)) ; find the peak response and call it " "Gain" "",
    ".meas AC Fcut TRIG mag(V(out))=Gain/sqrt(2) FALL=last",
)

callback_task = runner.run(netlist, run_filename="no_callback.net")
if callback_task is None:
    raise RuntimeError("Simulation task failed to start")
results = callback_task.wait_results()
if not isinstance(results, tuple):
    raise RuntimeError("Expected raw/log tuple from simulation run")
raw_path, log_path = cast(tuple[Path | None, Path | None], results)
if raw_path is None or log_path is None:
    raise RuntimeError("Simulation did not produce raw/log files")
processing_data(raw_path, log_path, supply_voltage=0, opamp="0")

if use_run_now is False:
    results = runner.wait_completion(1, abort_all_on_timeout=True)

    # Sim Statistics
    print(
        "Successful/Total Simulations: " + str(runner.okSim) + "/" + str(runner.runno)
    )
