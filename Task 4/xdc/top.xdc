
# FPGA: xc7z010clg400-1
# Board: Digilent Zybo Z7-10 Rev. B

# Inputs: Switches
set_property PACKAGE_PIN G15 [get_ports {a}]
set_property PACKAGE_PIN P15 [get_ports {b}]
set_property PACKAGE_PIN W13 [get_ports {cin}]

# Outputs: LEDs
set_property PACKAGE_PIN M14 [get_ports {sum}]
set_property PACKAGE_PIN M15 [get_ports {cout}]

# 3.3 V I/O standard
set_property IOSTANDARD LVCMOS33 [get_ports {a b cin sum cout}]
