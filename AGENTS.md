# Agent Behavioral Contract

## Goal
Generate synthesizable Verilog RTL from YAML hardware specifications
and repair errors iteratively using compiler and simulator feedback.

## Rules — must hold across all iterations

1. Preserve the EXACT module signature from the specification.
   Do not rename, add, or remove any ports.

2. Use synthesizable constructs only.
   No #delays. No $display in synthesizable modules.
   No non-synthesizable initial blocks.

3. Do NOT modify the testbench file under any circumstances.

4. When debugging, change ONLY the RTL file.

5. Follow the reset behavior described in the spec exactly
   (synchronous vs asynchronous, active high vs active low).