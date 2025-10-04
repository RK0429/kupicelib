from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, "..")  # This is to allow the import from the kupicelib folder

from kupicelib import SimRunner, SpiceEditor
from kupicelib.sim.process_callback import (
    ProcessCallback,  # Importing the ProcessCallback class type
)


class CallbackProc(ProcessCallback):
    """Class encapsulating the callback function.

    It can have whatever name.
    """

    @staticmethod
    def callback(
        raw_file: str | Path,
        log_file: str | Path,
        **kwargs: Any,
    ) -> str:
        raw_path = Path(raw_file)
        log_path = Path(log_file)
        print(
            "Handling the simulation data of "
            f"{raw_path}"
            ", log file "
            f"{log_path}"
        )
        # Doing some processing here
        if kwargs:
            print(f"Additional arguments: {kwargs}")
        return f"Parsed Result of {raw_path}, log file {log_path}"


if __name__ == "__main__":
    from kupicelib.simulators.ltspice_simulator import LTspice

    runner = SimRunner(
        output_folder="./temp_batch4", simulator=LTspice
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
    netlist.set_component_value(
        "XU1:C2", 20e-12
    )  # modifying a component in a subcircuit
    # define simulation
    netlist.add_instructions("; Simulation settings", ";.param run = 0")
    netlist.set_parameter("run", 0)

    for opamp in (
        "AD712",
        "AD820_XU1",
    ):  # don't use AD820, it is defined in the file and will mess up newer LTspice versions
        netlist["XU1"].model = opamp
        for supply_voltage in (5, 10, 15):
            netlist["V1"].value = supply_voltage
            netlist["V2"].value = -supply_voltage
            # overriding the automatic netlist naming
            run_netlist_file = f"{netlist.netlist_file.stem}_{opamp}_{supply_voltage}.net"
            runner.run(netlist, run_filename=run_netlist_file, callback=CallbackProc)

    for result in runner:
        print(result)  # Prints the result of the callback function

    netlist.reset_netlist()
    netlist.add_instructions(  # Adding additional instructions
        "; Simulation settings",
        ".ac dec 30 10 1Meg",
        ".meas AC Gain MAX mag(V(out)) ; find the peak response and call it " "Gain" "",
        ".meas AC Fcut TRIG mag(V(out))=Gain/sqrt(2) FALL=last",
    )

    raw, log = runner.run_now(netlist, run_filename="no_callback.net")
    if raw is None or log is None:
        raise RuntimeError("Synchronous run did not produce raw/log files")
    CallbackProc.callback(raw, log)

    results = runner.wait_completion(1, abort_all_on_timeout=True)

    # Sim Statistics
    print(
        "Successful/Total Simulations: " + str(runner.okSim) + "/" + str(runner.runno)
    )
