from kupicelib import RawRead
from kupicelib.editor.spice_editor import SpiceEditor
from kupicelib.sim.sim_runner import SimRunner
from kupicelib.simulators.qspice_simulator import Qspice
from kupicelib.utils.sweep_iterators import sweep_log


def processing_data(raw_file, log_file):
    print(f"Handling the simulation data of {raw_file}, log file {log_file}")
    raw_data = RawRead(raw_file)
    vout = raw_data.get_wave("V(out)")
    return raw_file, vout.max()


# select spice model
runner = SimRunner(
    output_folder="./temp",
    simulator=Qspice.create_from("C:/Program Files/QSPICE/QSPICE64.exe"),
)
netlist = SpiceEditor("./testfiles/testfile.net")
# set default arguments
netlist["R1"].value = "4k"
netlist["V1"].model = (
    "SINE(0 1 3k 0 0 0)"  # Modifying the behavior of the voltage source
)
netlist.add_instruction(".tran 1n 3m")
netlist.add_instruction(".plot V(out)")
netlist.add_instruction(
    ".save V(*?*) I*(*?*))"
)  # Saves just the first level currents and voltages

sim_no = 1
# .step dec param cap 1p 10u 1
for cap in sweep_log(1e-12, 10e-6, 10):
    netlist["C1"].value = cap
    runner.run(
        netlist, callback=processing_data, run_filename=f"testfile_qspice_{sim_no}.net"
    )
    sim_no += 1

# Reading the data
results = {}
for raw_file, vout_max in runner:  # Iterate over the results of the callback function
    results[raw_file.name] = vout_max
# The block above can be replaced by the following line
# results = {raw_file.name: vout_max for raw_file, vout_max in runner}

print(results)

# Sim Statistics
print("Successful/Total Simulations: " + str(runner.okSim) + "/" + str(runner.runno))
input("Press Enter to delete simulation files...")
runner.cleanup_files()
