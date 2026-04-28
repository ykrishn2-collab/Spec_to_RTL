# SpecToGDS

SpecToGDS is a small research-style repository for turning YAML hardware specifications into Verilog RTL, validating the RTL against testbenches, and in the more advanced flows pushing the design through synthesis, OpenROAD physical design, gate-level simulation, timing closure, and power/timing tradeoff exploration.

The repo contains three related workflows:

- `agent.py`: the simplest Spec-to-RTL repair loop for behavioral correctness.
- `agent_full_flow.py` and `agent_codex_orchestrated.py`: end-to-end Spec-to-GDS style flows that include backend closure.
- `codex_tradeoff_agent/` and `Power_Optimization/`: timing and power tradeoff exploration flows built around repeated OpenROAD runs.

## What Is In This Repo

- YAML design specs in `specs/`
- Verilog/SystemVerilog testbenches in `tb/`
- Generated or repaired RTL in `rtl/`
- Behavioral and backend run logs in `logs/`
- Power optimization scripts and checked-in result artifacts in `Power_Optimization/`
- A second copy of the power/timing tradeoff flow in `codex_tradeoff_agent/`

The checked-in examples currently center on these designs:

- `p1`: sequence detector
- `p7`: pipelined fixed-point exponential
- `p9`: FIR filter
- `p5`: additional spec variants used by the full-flow scripts

## Repository Layout

```text
SpecToGDS/
|-- agent.py
|-- agent_full_flow.py
|-- agent_codex_orchestrated.py
|-- specs/
|-- tb/
|-- rtl/
|-- logs/
|-- codex_tradeoff_agent/
|-- Power_Optimization/
|-- README_agent_full_flow.md
`-- README_agent_codex_orchestrated.md
```

Key directories:

- `specs/`: YAML problem statements with module signature, ports, reset behavior, and timing target.
- `tb/`: simulation testbenches matched to the specs.
- `rtl/`: generated or optimized RTL snapshots.
- `logs/`: checked-in evidence from selected runs such as `p1`, `p9`, and `p7_full_flow`.
- `codex_tradeoff_agent/`: scripts for timing-closure plus fixed-period sweep plus optimized-point reruns.
- `Power_Optimization/`: a checked-in snapshot of the tradeoff flow together with `p7_optimization_results/`.

## Workflow Overview

### 1. Basic Spec-to-RTL Repair Loop

`agent.py` is the simplest entry point. It:

1. Reads a YAML spec.
2. Asks Codex to summarize the design intent.
3. Generates initial RTL.
4. Compiles with `iverilog`.
5. Runs simulation with `vvp`.
6. Feeds compile or simulation failures back to Codex for RTL repair.

This script currently runs two hardcoded problems:

- `specs/p1.yaml` with `tb/iclad_seq_detector_tb.v`
- `specs/p9.yaml` with `tb/iclad_fir_tb.v`

Run it from the repo root:

```powershell
python agent.py
```

Outputs are written under `logs/p1/` and `logs/p9/`, and generated RTL is written to `rtl/p1_design.v` and `rtl/p9_design.v`.

### 2. Full RTL-to-GDS Flow

`agent_full_flow.py` extends the loop to backend implementation. It can:

- generate or reuse RTL
- repair behavioral failures
- emit OpenROAD config and SDC collateral
- run synthesis with multiple strategies
- run OpenROAD place/route
- run synthesized and post-route gate-level simulation
- iterate RTL when timing, GLS, or backend closure fails

Example:

```powershell
python agent_full_flow.py `
  --spec specs/p7.yaml `
  --tb tb/iclad_exp_tb.v `
  --rtl rtl/p7_design.v `
  --logs logs/p7_full_flow `
  --openroad-root openroad
```

If you already have a starting RTL file:

```powershell
python agent_full_flow.py `
  --spec specs/p7.yaml `
  --tb tb/iclad_exp_tb.v `
  --rtl rtl/p7_design.v `
  --logs logs/p7_full_flow `
  --openroad-root openroad `
  --reuse-existing-rtl
```

`README_agent_full_flow.md` contains more script-specific notes.

### 3. Codex-Orchestrated Full Flow

`agent_codex_orchestrated.py` runs the same broad backend flow, but delegates more of the orchestration to Codex, including strategy selection, report interpretation, and backend failure classification.

Example:

```powershell
python agent_codex_orchestrated.py `
  --spec specs/p7.yaml `
  --tb tb/iclad_exp_tb.v `
  --rtl rtl/p7_design.v `
  --logs logs/p7_orchestrated `
  --openroad-root openroad
```

`README_agent_codex_orchestrated.md` documents this version in more detail.

### 4. Timing and Power Tradeoff Flow

The tradeoff flow is available in two places:

- `codex_tradeoff_agent/`: the script set itself
- `Power_Optimization/`: the same style of flow plus checked-in `p7_optimization_results/`

This flow can:

- generate initial RTL
- close timing at a target minimum period
- sweep one fixed RTL across multiple clock periods
- compare worst slack against power
- run a second single-point optimization against the baseline sweep

Example full tradeoff run:

```powershell
python codex_tradeoff_agent\agent_tradeoff_flow.py `
  --spec specs/p7.yaml `
  --tb tb/iclad_exp_tb.v `
  --workspace tradeoff_run `
  --periods 7 6.5 6 5.5 5 4.5 4 3.5 3 `
  --opt-target-period 3.0
```

The checked-in results under `Power_Optimization/p7_optimization_results/` include:

- initial RTL
- minimum-period closure artifacts
- fixed-RTL sweep results
- optimized-point results
- summary files and SVG plots

## Requirements

The scripts assume a Windows host with WSL-based backend tools. The exact paths are hardcoded in the Python files and should be treated as local-environment assumptions, not portable defaults.

Typical requirements across the flows:

- Python 3
- Codex CLI available on `PATH`, or under `%APPDATA%\npm\codex.cmd`
- `iverilog`
- `vvp`
- `pyyaml` for robust YAML parsing
- WSL with distro name `Ubuntu`
- OpenROAD-flow-scripts
- OpenROAD
- Yosys

Hardcoded backend defaults referenced by the advanced scripts include paths like:

- `/home/kyash/OpenROAD-flow-scripts-master/flow`
- `/home/kyash/OpenROAD/install-clean/bin/openroad`
- `/usr/local/bin/yosys`

If you run this on another machine, update those constants near the tops of:

- `agent_full_flow.py`
- `agent_codex_orchestrated.py`
- `codex_tradeoff_agent/fixed_rtl_sweep.py`
- `codex_tradeoff_agent/optimize_single_point.py`
- `Power_Optimization/fixed_rtl_sweep.py`
- `Power_Optimization/optimize_single_point.py`

## Checked-In Artifacts

This repo intentionally contains generated artifacts, not just source code.

Notable checked-in outputs:

- `logs/p1/` and `logs/p9/`: behavioral-flow logs from the simple repair loop
- `logs/p7_full_flow/`: full-flow logs, timing summaries, GLS logs, backend reports, and best RTL snapshot
- `Power_Optimization/p7_optimization_results/`: power/timing tradeoff experiment outputs

At the same time, `.gitignore` still ignores new `logs/` content by default, so future log directories will not be tracked unless they are force-added explicitly.

## Current Example Outcome

The checked-in `logs/p7_full_flow/final_status.txt` shows a successful `p7` backend run with:

- `status=PASS`
- `period_min=3.17`
- `wns=0.0`
- `tns=0.0`
- generated GDS and synthesized/closed netlists under `openroad/p7/` paths recorded in the summary

The checked-in `Power_Optimization/p7_optimization_results/summary.txt` links the main tradeoff outputs:

- initial RTL
- timing-closing RTL
- fixed-period sweep
- optimized point
- baseline and overlay plots

## Notes

- These flows are agent-driven and call the Codex CLI directly.
- The scripts are designed to preserve the module signature from the YAML spec and avoid changing testbenches.
- The repository mixes source code with experiment artifacts; it is closer to a project notebook plus automation scripts than to a clean library package.
