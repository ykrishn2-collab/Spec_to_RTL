# agent_full_flow.py

`agent_full_flow.py` is a single-design RTL-to-backend automation script. It generates or reuses RTL, fixes behavioral failures with Codex, runs synthesis and backend through OpenROAD-flow-scripts, checks gate-level simulation, and iterates RTL when synthesis, GLS, backend, or timing closure fails.

## Requirements

Run from the repository root, for example `C:\Users\kyash\spec2rtl_agent`.

The script expects:

- Codex CLI on `PATH`, or in `%APPDATA%\npm\codex.cmd`.
- `iverilog` and `vvp` on `PATH`.
- Python package `pyyaml`, unless the simple fallback parser supports your spec.
- WSL distro named `Ubuntu`.
- OpenROAD-flow-scripts at `/home/kyash/OpenROAD-flow-scripts-master/flow`.
- OpenROAD at `/home/kyash/OpenROAD/install-clean/bin/openroad`.
- Yosys at `/usr/local/bin/yosys`.

The WSL/OpenROAD/Yosys paths are hardcoded near the top of `agent_full_flow.py`. If you run this on a different system, update these constants before starting:

```python
DEFAULT_WSL_DISTRO = "Ubuntu"
DEFAULT_ORFS = "/home/kyash/OpenROAD-flow-scripts-master/flow"
DEFAULT_OPENROAD_EXE = "/home/kyash/OpenROAD/install-clean/bin/openroad"
DEFAULT_YOSYS_EXE = "/usr/local/bin/yosys"
```

Set `DEFAULT_WSL_DISTRO` to your WSL distribution name, `DEFAULT_ORFS` to your OpenROAD-flow-scripts `flow` directory, `DEFAULT_OPENROAD_EXE` to your OpenROAD binary, and `DEFAULT_YOSYS_EXE` to your Yosys binary.

## Basic Usage

Generate or overwrite RTL, then run the full behavioral, synthesis, GLS, backend, and timing loop:

```powershell
python agent_full_flow.py `
  --spec specs/p7.yaml `
  --tb tb/iclad_exp_tb.v `
  --rtl rtl/p7_design.v `
  --logs logs/p7_fullflow `
  --openroad-root openroad
```

Reuse an existing RTL file instead of asking Codex to generate initial RTL:

```powershell
python agent_full_flow.py `
  --spec specs/p7.yaml `
  --tb tb/iclad_exp_tb.v `
  --rtl rtl/p7_design.v `
  --logs logs/p7_fullflow `
  --openroad-root openroad `
  --reuse-existing-rtl
```

## Arguments

- `--spec`: YAML spec containing the module signature, ports, and clock period.
- `--tb`: Verilog testbench. The script does not intentionally modify it.
- `--rtl`: RTL file to generate, reuse, and iteratively modify.
- `--logs`: output directory for logs, status files, reports, and best RTL snapshots.
- `--openroad-root`: local workspace for generated OpenROAD collateral. Default is `openroad`.
- `--reuse-existing-rtl`: skip initial RTL generation and start from the existing `--rtl` file.

## What It Does

The script runs these stages:

1. Parse the YAML spec and module signature.
2. Generate initial RTL with Codex unless `--reuse-existing-rtl` is set.
3. Compile and simulate the RTL with `iverilog` and `vvp`.
4. Ask Codex to fix RTL compile or simulation failures.
5. Write `constraint.sdc` and `config.mk` for OpenROAD-flow-scripts.
6. Try several Yosys synthesis strategies.
7. Run gate-level simulation on the synthesized netlist.
8. Run OpenROAD backend attempts, adjusting floorplan knobs after placement/routing failures.
9. Collect timing reports, GDS, DEF, SDC, netlists, and logs.
10. Ask Codex to fix RTL if synthesis, GLS, backend, or timing closure fails.

Iteration limits are set near the top of the script:

```python
MAX_RTL_ITERS = 5
MAX_SYNTH_ITERS = 5
MAX_BACKEND_ITERS = 3
MAX_RTL_GEN_ATTEMPTS = 3
```

## Outputs

The `--logs` directory receives the main run evidence:

- `behavioral_status.txt`: behavioral pass/fail.
- `compile_*.log` and `sim_*.log`: RTL compile and simulation logs.
- `synth_*.log`: synthesis logs.
- `backend_*.log`: OpenROAD backend logs.
- `gls_synth_compile.log`, `gls_synth_run.log`, `gls_closed_compile.log`, `gls_closed_run.log`: gate-level checks.
- `timing_summary.txt`: latest timing metrics.
- `best_timing_summary.txt`: best timing point found.
- `best_rtl.v`: RTL snapshot for the best timing point.
- `final_status.txt`: final pass/fail summary.
- `finish*.rpt`: copied OpenROAD finish reports when available.

The `--openroad-root` workspace stores generated backend collateral under `<openroad-root>\<problem_stem>\`, including:

- `config.mk`
- `constraint.sdc`
- `out\`
- `gls\`
- `sky130_fd_sc_hd_models\`

## Notes

- The script calls Codex with `--dangerously-bypass-approvals-and-sandbox` and `--skip-git-repo-check`.
- It may clone Sky130 HD model files into the OpenROAD workspace if they are missing.
- Keep the spec, RTL module signature, and testbench aligned. The flow is designed to preserve the module signature and avoid adding ports.
