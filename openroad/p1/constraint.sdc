create_clock -name clk -period 1.0 [get_ports clk]
set_input_delay 0.5 -clock clk [get_ports reset]
set_input_delay 0.5 -clock clk [get_ports data_in]
set_output_delay 0.5 -clock clk [get_ports detected]
