# agent_codex_orchestrated.py

`agent_codex_orchestrated.py` is a Codex-heavy version of the full RTL-to-backend flow. It still runs one design from spec and testbench through RTL repair, synthesis, gate-level simulation, OpenROAD backend, and timing closure, but it asks Codex to help with more orchestration steps such as command planning, synthesis strategy selection, SDC/config rendering, report analysis, and backend failure classification.

Use this script when you want more Codex involvement in the flow mechanics. Use `agent_full_flow.py` when you want the more direct deterministic Python implementation.

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

The WSL/OpenROAD/Yosys paths are hardcoded near the top of `agent_codex_orchestrated.py`. If you run this on a different system, update these constants before starting:

```python
DEFAULT_WSL_DISTRO = "Ubuntu"
DEFAULT_ORFS = "/home/kyash/OpenROAD-flow-scripts-master/flow"
DEFAULT_OPENROAD_EXE = "/home/kyash/OpenROAD/install-clean/bin/openroad"
DEFAULT_YOSYS_EXE = "/usr/local/bin/yosys"
```

Set `DEFAULT_WSL_DISTRO` to your WSL distribution name, `DEFAULT_ORFS` to your OpenROAD-flow-scripts `flow` directory, `DEFAULT_OPENROAD_EXE` to your OpenROAD binary, and `DEFAULT_YOSYS_EXE` to your Yosys binary.

## Basic Usage

Generate or overwrite RTL, then run the Codex-orchestrated behavioral, synthesis, GLS, backend, and timing loop:

```powershell
python agent_codex_orchestrated.py `
  --spec specs/p7.yaml `
  --tb tb/iclad_exp_tb.v `
  --rtl rtl/p7_design.v `
  --logs logs/p7_orchestrated `
  --openroad-root openroad
```

Reuse an existing RTL file instead of asking Codex to generate initial RTL:

```powershell
python agent_codex_orchestrated.py `
  --spec specs/p7.yaml `
  --tb tb/iclad_exp_tb.v `
  --rtl rtl/p7_design.v `
  --logs logs/p7_orchestrated `
  --openroad-root openroad `
  --reuse-existing-rtl
```

## Arguments

- `--spec`: YAML spec containing the module signature, ports, and clock period.
- `--tb`: Verilog testbench. The script does not intentionally modify it.
- `--rtl`: RTL file to generate, reuse, and iteratively modify.
- `--logs`: output directory for logs, status files, reports, analyses, and best RTL snapshots.
- `--openroad-root`: local workspace for generated OpenROAD collateral. Default is `openroad`.
- `--reuse-existing-rtl`: skip initial RTL generation and start from the existing `--rtl` file.

## What It Does

The script runs these stages:

1. Parse the YAML spec and module signature.
2. Generate initial RTL with Codex unless `--reuse-existing-rtl` is set.
3. Compile and simulate the RTL with `iverilog` and `vvp`.
4. Ask Codex to fix RTL compile or simulation failures.
5. Ask Codex to help prepare synthesis strategies.
6. Ask Codex to render or validate `constraint.sdc` and `config.mk`, with Python fallbacks.
7. Ask Codex to plan execution commands, then run synthesis and backend commands.
8. Run gate-level simulation on synthesized and closed netlists.
9. Ask Codex to analyze finish reports and classify backend failures.
10. Ask Codex to fix RTL when timing or backend closure fails.

Iteration limits are set near the top of the script:

```python
MAX_RTL_ITERS = 5
MAX_SYNTH_ITERS = 5
MAX_BACKEND_ITERS = 1
```

`MAX_BACKEND_ITERS` is lower than in `agent_full_flow.py`; this script relies more on Codex-guided RTL and strategy changes across full iterations.

## Outputs

The `--logs` directory receives the main run evidence:

- `behavioral_status.txt`: behavioral pass/fail.
- `compile_*.log` and `sim_*.log`: RTL compile and simulation logs.
- `synth_strategy_*.txt`: selected synthesis strategy for an attempt.
- `synth_*.log`: synthesis logs.
- `backend_*.log`: OpenROAD backend logs.
- `backend_*_analysis.txt`: Codex backend failure analysis when a backend run fails.
- `finish*_analysis.txt`: Codex timing/report analysis when finish reports are available.
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
