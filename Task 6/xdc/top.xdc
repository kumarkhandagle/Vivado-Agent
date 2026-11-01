
## Clock - 125 MHz
set_property PACKAGE_PIN K17 [get_ports clk]
set_property IOSTANDARD LVCMOS33 [get_ports clk]

create_clock -period 8.000 -name sys_clk [get_ports clk]

## Reset - BTN0
set_property PACKAGE_PIN K18 [get_ports rst]
set_property IOSTANDARD LVCMOS33 [get_ports rst]

## Data Input - SW0
set_property PACKAGE_PIN G15 [get_ports d]
set_property IOSTANDARD LVCMOS33 [get_ports d]

## Output - LED0
set_property PACKAGE_PIN M14 [get_ports q]
set_property IOSTANDARD LVCMOS33 [get_ports q]
