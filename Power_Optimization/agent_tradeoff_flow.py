import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent


def find_codex() -> Optional[str]:
    codex = shutil.which("codex")
    if codex:
        return codex
    possible = [
        Path.home() / "AppData" / "Roaming" / "npm" / "codex.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "codex.CMD",
    ]
    for path in possible:
        if path.exists():
            return str(path)
    return None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_codex(prompt: str, cwd: Path) -> int:
    codex_cmd = find_codex()
    if not codex_cmd:
        raise RuntimeError("Could not find Codex CLI.")
    result = subprocess.run(
        [
            codex_cmd,
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            "-",
        ],
        input=prompt,
        text=True,
        cwd=cwd,
    )
    return result.returncode


def run_python(script: Path, args: List[str], cwd: Path) -> None:
    cmd = [sys.executable, str(script), *args]
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")


def verify_behavioral(rtl_path: Path, tb_path: Path, out_dir: Path) -> None:
    exe_path = out_dir / "behavioral_check.exe"
    compile_result = subprocess.run(
        ["iverilog", "-g2012", "-o", str(exe_path), str(rtl_path), str(tb_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    write_text(out_dir / "iverilog.log", f"STDOUT:\n{compile_result.stdout}\nSTDERR:\n{compile_result.stderr}")
    if compile_result.returncode != 0:
        raise RuntimeError("Behavioral compile failed.")

    run_result = subprocess.run(
        ["vvp", str(exe_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    write_text(out_dir / "vvp.log", f"STDOUT:\n{run_result.stdout}\nSTDERR:\n{run_result.stderr}")
    if run_result.returncode != 0 or "PASS" not in run_result.stdout:
        raise RuntimeError("Behavioral simulation failed.")


def build_generate_prompt(spec_path: Path, rtl_path: Path) -> str:
    agents_path = REPO_ROOT / "AGENTS.md"
    agents_text = read_text(agents_path) if agents_path.exists() else ""
    return f"""
You are generating an initial RTL implementation that will be iteratively optimized to close timing.

Repository rules:
{agents_text}

Task:
- Read {spec_path}
- Generate synthesizable Verilog RTL and write it to {rtl_path}
- Preserve the EXACT module signature from the spec
- Do NOT add ports
- Use synthesizable constructs only
- Follow reset behavior exactly
- Do not modify any testbench
- Prefer low combinational depth and low area
- Only modify {rtl_path}
- Do not run simulation
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Codex-driven min-period closure flow, fixed-RTL sweep, and optimized-point run.")
    parser.add_argument("--spec", required=True, help="Base YAML spec")
    parser.add_argument("--tb", required=True, help="Testbench path")
    parser.add_argument("--workspace", default=str(ROOT / "artifacts"), help="Output workspace root")
    parser.add_argument("--periods", nargs="+", type=float, default=[7.0, 6.5, 6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0])
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--max-rtl-iters", type=int, default=4)
    parser.add_argument("--opt-target-period", type=float)
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    tb_path = Path(args.tb).resolve()
    workspace = Path(args.workspace).resolve()
    initial_rtl_dir = workspace / "initial_rtl"
    opt_dir = workspace / "min_period_closure"
    sweep_dir = workspace / "fixed_rtl_sweep"
    point_dir = workspace / "optimized_point"
    initial_rtl_path = initial_rtl_dir / f"{spec_path.stem}_initial.v"
    min_period = min(args.periods)
    opt_target_period = args.opt_target_period if args.opt_target_period is not None else min_period

    initial_rtl_dir.mkdir(parents=True, exist_ok=True)
    opt_dir.mkdir(parents=True, exist_ok=True)
    sweep_dir.mkdir(parents=True, exist_ok=True)
    point_dir.mkdir(parents=True, exist_ok=True)

    if not args.skip_generate:
        if initial_rtl_path.exists():
            initial_rtl_path.unlink()
        write_text(initial_rtl_path, "")
        rc = run_codex(build_generate_prompt(spec_path, initial_rtl_path), REPO_ROOT)
        if rc != 0:
            raise RuntimeError("Codex initial RTL generation failed.")

    verify_behavioral(initial_rtl_path, tb_path, initial_rtl_dir)

    run_python(
        ROOT / "optimize_single_point.py",
        [
            "--spec",
            str(spec_path),
            "--tb",
            str(tb_path),
            "--seed-rtl",
            str(initial_rtl_path),
            "--out-dir",
            str(opt_dir),
            "--target-period",
            str(min_period),
            "--max-rtl-iters",
            str(args.max_rtl_iters),
        ],
        REPO_ROOT,
    )

    closing_rtl = opt_dir / f"{initial_rtl_path.stem}_optimized.v"
    verify_behavioral(closing_rtl, tb_path, opt_dir)

    run_python(
        ROOT / "fixed_rtl_sweep.py",
        [
            "--spec",
            str(spec_path),
            "--rtl",
            str(closing_rtl),
            "--out-dir",
            str(sweep_dir),
            "--periods",
            *[str(period) for period in args.periods],
        ],
        REPO_ROOT,
    )

    run_python(
        ROOT / "optimize_single_point.py",
        [
            "--spec",
            str(spec_path),
            "--tb",
            str(tb_path),
            "--seed-rtl",
            str(closing_rtl),
            "--baseline-csv",
            str(sweep_dir / "results.csv"),
            "--out-dir",
            str(point_dir),
            "--target-period",
            str(opt_target_period),
            "--max-rtl-iters",
            str(args.max_rtl_iters),
        ],
        REPO_ROOT,
    )

    write_text(
        workspace / "summary.txt",
        "\n".join(
            [
                f"initial_rtl={initial_rtl_path}",
                f"closing_rtl={closing_rtl}",
                f"min_period_closure={opt_dir}",
                f"fixed_rtl_sweep={sweep_dir}",
                f"optimized_point={point_dir}",
                f"baseline_plot={sweep_dir / 'worst_slack_vs_power.svg'}",
                f"optimized_overlay={point_dir / 'overlay_worst_slack_vs_power.svg'}",
                "",
            ]
        ),
    )


if __name__ == "__main__":
    main()
