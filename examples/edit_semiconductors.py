import kupicelib

netlist = kupicelib.SpiceEditor("./testfiles/amp3/amp3.net")
print("Before")
parameter_items = netlist.get_subcircuit("XOPAMP").get_component_parameters("M00").items()
print(f"XOPAMP:M00 params={parameter_items}")
newsettings = {"W": 10e-6}
netlist.get_subcircuit("XOPAMP").set_component_parameters("M00", **newsettings)
# or: netlist.get_subcircuit("XOPAMP").set_component_parameters("M00", W=10E-6)
print("After")
parameter_items = netlist.get_subcircuit("XOPAMP").get_component_parameters("M00").items()
print(f"XOPAMP:M00 params={parameter_items}")
