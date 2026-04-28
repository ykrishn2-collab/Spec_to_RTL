# codex_tradeoff_agent

`codex_tradeoff_agent` runs a Codex-driven RTL timing and power tradeoff flow for one YAML spec and testbench.

The flow can:

1. Generate initial RTL with the Codex CLI.
2. Verify behavior with `iverilog` and `vvp`.
3. Optimize that RTL at the minimum requested clock period.
4. Freeze the timing-closing RTL and sweep it across clock periods.
5. Plot worst slack versus total power.
6. Run a second single-point optimization against the baseline sweep, usually to reduce power at a target period.

## Requirements

Run from the repository root, for example `C:\Users\kyash\spec2rtl_agent`.

The scripts expect:

- Codex CLI on `PATH`, or in `%APPDATA%\npm\codex.cmd`.
- `iverilog` and `vvp` on `PATH`.
- WSL distro named `Ubuntu`.
- OpenROAD-flow-scripts at `/home/kyash/OpenROAD-flow-scripts-master/flow`.
- OpenROAD at `/home/kyash/OpenROAD/install-clean/bin/openroad`.
- Yosys at `/usr/local/bin/yosys`.

The WSL/OpenROAD paths are currently hardcoded in `optimize_single_point.py` and `fixed_rtl_sweep.py`. If you run this on a different system, update these constants near the top of both files before starting a flow:

```python
DISTRO = "Ubuntu"
ORFS = "/home/kyash/OpenROAD-flow-scripts-master/flow"
OPENROAD_EXE = "/home/kyash/OpenROAD/install-clean/bin/openroad"
YOSYS_EXE = "/usr/local/bin/yosys"
```

Set `DISTRO` to your WSL distribution name, `ORFS` to your OpenROAD-flow-scripts `flow` directory, `OPENROAD_EXE` to your OpenROAD binary, and `YOSYS_EXE` to your Yosys binary.

## Full Flow

Use `agent_tradeoff_flow.py` when you want to generate initial RTL, close timing, sweep fixed RTL, and run the optimized point in one command.

```powershell
python codex_tradeoff_agent\agent_tradeoff_flow.py `
  --spec specs/p7.yaml `
  --tb tb/iclad_exp_tb.v `
  --workspace separate_p7_fullflow_run2 `
  --periods 7 6.5 6 5.5 5 4.5 4 3.5 3 `
  --opt-target-period 3.0
```

Useful options:

- `--workspace`: output directory. Default is `codex_tradeoff_agent\artifacts`.
- `--periods`: clock periods to sweep. The minimum value is also used for the first timing-closure optimization.
- `--opt-target-period`: target period for the final optimized point. Defaults to the minimum period.
- `--max-rtl-iters`: maximum Codex RTL optimization iterations. Default is `4`.
- `--skip-generate`: reuse the expected initial RTL file instead of generating it.

## Full Flow Outputs

For a workspace such as `separate_p7_fullflow_run2`, the main outputs are:

- `initial_rtl\`: generated starting RTL plus behavioral check logs.
- `min_period_closure\`: timing-closure optimization from the initial RTL.
- `fixed_rtl_sweep\`: fixed-RTL OpenROAD runs for each requested period.
- `fixed_rtl_sweep\results.csv`: baseline sweep metrics.
- `fixed_rtl_sweep\worst_slack_vs_power.svg`: baseline plot.
- `optimized_point\`: final single-point optimization against the baseline curve.
- `optimized_point\overlay_worst_slack_vs_power.svg`: baseline curve plus optimized point.
- `summary.txt`: paths to the main generated artifacts.

## Rerun One Optimized Point

Use `optimize_single_point.py` when you already have a seed RTL and want another optimized run, for example `optimized_point_powerfix3`.

```powershell
python codex_tradeoff_agent\optimize_single_point.py `
  --spec specs/p7.yaml `
  --tb tb/iclad_exp_tb.v `
  --seed-rtl separate_p7_fullflow_run2\min_period_closure\p7_initial_optimized.v `
  --baseline-csv separate_p7_fullflow_run2\fixed_rtl_sweep\results.csv `
  --out-dir separate_p7_fullflow_run2\optimized_point_powerfix3 `
  --target-period 3.0 `
  --max-rtl-iters 4
```

If `--baseline-csv` is provided, the optimizer treats the nearest baseline point as a power reference and writes an overlay SVG. If it is omitted, the script optimizes for timing closure only and stops after the first passing timing result.

Outputs include:

- `iterations\iter_XX\...`: RTL snapshots, behavioral logs, and backend attempts.
- `iterations\iter_XX\backend_attempts\attempt_base|attempt_spread|attempt_wide\`: OpenROAD configs, logs, metrics, and reports.
- `iteration_results.csv`: best backend attempt per RTL iteration.
- `result.csv`: selected best point.
- `<seed_stem>_optimized.v`: selected optimized RTL.
- `summary.txt`: selected RTL and metrics.

## Sweep One Fixed RTL

Use `fixed_rtl_sweep.py` when you only want a clock-period sweep for an existing RTL.

```powershell
python codex_tradeoff_agent\fixed_rtl_sweep.py `
  --spec specs/p7.yaml `
  --rtl separate_p7_fullflow_run2\min_period_closure\p7_initial_optimized.v `
  --out-dir separate_p7_fullflow_run2\fixed_rtl_sweep_rerun `
  --periods 7 6.5 6 5.5 5 4.5 4 3.5 3
```

This writes one run folder per period under `runs\period_*`, plus `results.csv`, `worst_slack_vs_power.svg`, and `summary.txt`.

## Notes

- The scripts call Codex with `--dangerously-bypass-approvals-and-sandbox` and `--skip-git-repo-check`.
- The RTL generation and optimization prompts preserve the module signature, avoid new ports, use synthesizable RTL, and do not modify the testbench.
- Backend runs use three physical presets named `base`, `spread`, and `wide`; the best attempt is selected by the script's scoring function.
