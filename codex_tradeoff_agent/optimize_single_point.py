import argparse
import csv
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
TOTAL_POWER_RE = re.compile(r"^Total\s+(?P<internal>[0-9.eE+-]+)\s+(?P<switching>[0-9.eE+-]+)\s+(?P<leakage>[0-9.eE+-]+)\s+(?P<total>[0-9.eE+-]+)")
CRITICAL_PATH_SLACK_RE = re.compile(r"critical path slack\s*\n-+\s*\n(?P<slack>-?[0-9.]+)", re.IGNORECASE)
DISTRO = "Ubuntu"
ORFS = "/home/kyash/OpenROAD-flow-scripts-master/flow"
OPENROAD_EXE = "/home/kyash/OpenROAD/install-clean/bin/openroad"
YOSYS_EXE = "/usr/local/bin/yosys"
BACKEND_PRESETS = [
    {"name": "base", "die_area": "0 0 240 240", "core_area": "30 30 210 210", "place_density": "0.35"},
    {"name": "spread", "die_area": "0 0 300 300", "core_area": "40 40 260 260", "place_density": "0.28"},
    {"name": "wide", "die_area": "0 0 360 360", "core_area": "50 50 310 310", "place_density": "0.22"},
]


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


def to_wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix().split(":", 1)[1]
    return f"/mnt/{drive}{rest}"


def run_wsl_bash(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["wsl", "-d", DISTRO, "--", "bash", "-lc", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def maybe_copy_wsl_file(src: str, dst: Path) -> bool:
    result = run_wsl_bash(f"test -f '{src}' && cat '{src}'")
    if result.returncode != 0:
        return False
    write_text(dst, result.stdout)
    return True


def parse_finish_report(path: Path) -> Dict[str, Optional[float]]:
    metrics: Dict[str, Optional[float]] = {
        "wns": None,
        "worst_slack": None,
        "period_min_ns": None,
        "fmax_mhz": None,
        "total_power_w": None,
    }
    if not path.exists():
        return metrics

    report_text = read_text(path)
    slack_match = CRITICAL_PATH_SLACK_RE.search(report_text)
    if slack_match:
        metrics["wns"] = float(slack_match.group("slack"))

    for line in report_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("worst slack max"):
            metrics["worst_slack"] = float(stripped.split()[-1])
        elif "period_min" in stripped and "fmax" in stripped:
            period_match = re.search(r"period_min\s*=\s*([0-9.]+)", stripped)
            fmax_match = re.search(r"fmax\s*=\s*([0-9.]+)", stripped)
            if period_match:
                metrics["period_min_ns"] = float(period_match.group(1))
            if fmax_match:
                metrics["fmax_mhz"] = float(fmax_match.group(1))
        power_match = TOTAL_POWER_RE.match(stripped)
        if power_match:
            metrics["total_power_w"] = float(power_match.group("total"))
    return metrics


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


def write_constraint_sdc(out_path: Path, target_period_ns: float) -> None:
    text = "\n".join(
        [
            f"create_clock -name clk -period {target_period_ns:g} [get_ports clk]",
            "set_input_delay 0.5 -clock clk [get_ports rst]",
            "set_input_delay 0.5 -clock clk [get_ports enable]",
            "set_input_delay 0.5 -clock clk [get_ports x_in]",
            "set_output_delay 0.5 -clock clk [get_ports exp_out]",
            "",
        ]
    )
    write_text(out_path, text)


def write_config_mk(rtl_path: Path, sdc_path: Path, config_path: Path, preset: Dict[str, str]) -> None:
    text = "\n".join(
        [
            "export DESIGN_NAME = exp_fixed_point",
            "export PLATFORM = sky130hd",
            "",
            f"export VERILOG_FILES = {to_wsl_path(rtl_path)}",
            f"export SDC_FILE = {to_wsl_path(sdc_path)}",
            "",
            f"export DIE_AREA = {preset['die_area']}",
            f"export CORE_AREA = {preset['core_area']}",
            f"export PLACE_DENSITY = {preset['place_density']}",
            "export TNS_END_PERCENT = 100",
            "",
        ]
    )
    write_text(config_path, text)


def build_prompt(
    spec_path: Path,
    seed_rtl: Path,
    opt_rtl: Path,
    baseline_csv: Optional[Path],
    target_period_ns: float,
    feedback_text: str,
) -> str:
    agents_path = REPO_ROOT / "AGENTS.md"
    agents_text = read_text(agents_path) if agents_path.exists() else ""
    baseline_section = ""
    if baseline_csv is not None and baseline_csv.exists():
        baseline_section = f"\nBaseline data:\n{read_text(baseline_csv)}\n"
    return f"""
You are optimizing RTL to close timing at a single target clock period, while keeping power low.

Repository rules:
{agents_text}

Files:
- Spec: {spec_path}
- Seed RTL: {seed_rtl}
- Output RTL to modify: {opt_rtl}

Task:
- Read the spec and seed RTL
- Optimize only {opt_rtl}
- Preserve the EXACT module signature
- Do NOT add ports
- Do NOT modify any testbench
- First priority: make this RTL close timing at {target_period_ns:g} ns
- Second priority: reduce power and combinational depth
- If the baseline data includes a point at {target_period_ns:g} ns, your goal is to beat that point on power while keeping timing closed
- You may pipeline or retime internally if the existing testbench still passes
- Keep the module synthesizable
{baseline_section}
Iteration feedback:
{feedback_text}
""".strip()


def summarize_metrics(point: Dict[str, object]) -> str:
    return "\n".join(
        [
            f"status={point.get('status')}",
            f"target_period_ns={point.get('target_period_ns')}",
            f"wns_ns={point.get('wns_ns')}",
            f"worst_slack={point.get('worst_slack')}",
            f"period_min_ns={point.get('period_min_ns')}",
            f"fmax_mhz={point.get('fmax_mhz')}",
            f"total_power_mw={point.get('total_power_mw')}",
            f"attempt_name={point.get('attempt_name')}",
        ]
    )


def score_point(point: Dict[str, object], power_priority: bool = False) -> tuple:
    backend_ok = 1 if point.get("status") == "PASS" else 0
    wns = float(point["wns_ns"]) if point.get("wns_ns") is not None else -1e9
    worst_slack = float(point["worst_slack"]) if point.get("worst_slack") is not None else -1e9
    power = float(point["total_power_mw"]) if point.get("total_power_mw") is not None else 1e9
    closed = 1 if wns >= 0.0 else 0
    if power_priority:
        return (backend_ok, closed, -power, wns, worst_slack)
    return (backend_ok, wns, worst_slack, -power)


def load_baseline_target(baseline_csv: Optional[Path], target_period_ns: float) -> Optional[Dict[str, float]]:
    if baseline_csv is None or not baseline_csv.exists():
        return None
    with baseline_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    best_match = None
    best_delta = None
    for row in rows:
        try:
            period = float(row["target_period_ns"])
        except (KeyError, TypeError, ValueError):
            continue
        delta = abs(period - target_period_ns)
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_match = row
    if best_match is None:
        return None
    result: Dict[str, float] = {"target_period_ns": float(best_match["target_period_ns"])}
    for key in ("wns_ns", "worst_slack", "period_min_ns", "total_power_mw"):
        try:
            result[key] = float(best_match[key])
        except (KeyError, TypeError, ValueError):
            continue
    return result


def build_overlay_svg(baseline_rows: List[Dict[str, str]], point: Dict[str, object], output_path: Path) -> None:
    valid_baseline = [
        row for row in baseline_rows
        if row.get("worst_slack") not in {"", None} and row.get("total_power_mw") not in {"", None}
    ]
    if point.get("worst_slack") is None or point.get("total_power_mw") is None:
        write_text(output_path, "<svg xmlns='http://www.w3.org/2000/svg' width='960' height='640'></svg>\n")
        return

    width = 960
    height = 640
    left = 90
    right = 50
    top = 40
    bottom = 90
    plot_w = width - left - right
    plot_h = height - top - bottom

    xs = [float(row["worst_slack"]) for row in valid_baseline] + [float(point["worst_slack"])]
    ys = [float(row["total_power_mw"]) for row in valid_baseline] + [float(point["total_power_mw"])]
    x_min = min(xs)
    x_max = max(xs)
    y_min = min(ys)
    y_max = max(ys)
    if math.isclose(x_min, x_max):
        x_min -= 0.1
        x_max += 0.1
    if math.isclose(y_min, y_max):
        y_min -= 0.1
        y_max += 0.1
    x_pad = max((x_max - x_min) * 0.1, 0.05)
    y_pad = max((y_max - y_min) * 0.1, 0.05)
    x0 = x_min - x_pad
    x1 = x_max + x_pad
    y0 = y_min - y_pad
    y1 = y_max + y_pad

    def sx(value: float) -> float:
        return left + (value - x0) * plot_w / (x1 - x0)

    def sy(value: float) -> float:
        return top + plot_h - (value - y0) * plot_h / (y1 - y0)

    baseline_sorted = sorted(valid_baseline, key=lambda row: float(row["worst_slack"]))
    baseline_points = " ".join(f"{sx(float(row['worst_slack'])):.1f},{sy(float(row['total_power_mw'])):.1f}" for row in baseline_sorted)
    px = sx(float(point["worst_slack"]))
    py = sy(float(point["total_power_mw"]))

    parts = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
        "<style>",
        "text { font-family: Arial, sans-serif; fill: #111; }",
        ".axis { stroke: #222; stroke-width: 2; }",
        ".grid { stroke: #d8d8d8; stroke-width: 1; }",
        ".tick { font-size: 12px; }",
        ".label { font-size: 14px; }",
        ".title { font-size: 20px; font-weight: bold; }",
        ".base { fill: none; stroke: #64748b; stroke-width: 2.5; }",
        ".base-point { fill: #64748b; }",
        ".opt-point { fill: #b91c1c; }",
        "</style>",
        f"<rect x='0' y='0' width='{width}' height='{height}' fill='#fcfcf8' />",
        f"<text class='title' x='{left}' y='28'>Optimized Point vs Baseline Worst Slack-Power Curve</text>",
    ]

    ticks = 5
    for i in range(ticks + 1):
        frac = i / ticks
        x_val = x0 + frac * (x1 - x0)
        y_val = y0 + frac * (y1 - y0)
        x = left + frac * plot_w
        y = top + plot_h - frac * plot_h
        parts.append(f"<line class='grid' x1='{x:.1f}' y1='{top}' x2='{x:.1f}' y2='{top + plot_h}' />")
        parts.append(f"<line class='grid' x1='{left}' y1='{y:.1f}' x2='{left + plot_w}' y2='{y:.1f}' />")
        parts.append(f"<text class='tick' x='{x:.1f}' y='{top + plot_h + 22}' text-anchor='middle'>{x_val:.2f}</text>")
        parts.append(f"<text class='tick' x='{left - 10}' y='{y + 4:.1f}' text-anchor='end'>{y_val:.2f}</text>")

    parts.append(f"<line class='axis' x1='{left}' y1='{top + plot_h}' x2='{left + plot_w}' y2='{top + plot_h}' />")
    parts.append(f"<line class='axis' x1='{left}' y1='{top}' x2='{left}' y2='{top + plot_h}' />")
    parts.append(f"<text class='label' x='{left + plot_w / 2:.1f}' y='{height - 24}' text-anchor='middle'>Worst Slack Max (ns)</text>")
    parts.append(
        f"<text class='label' x='24' y='{top + plot_h / 2:.1f}' text-anchor='middle' transform='rotate(-90 24 {top + plot_h / 2:.1f})'>Total Power (mW)</text>"
    )
    parts.append(f"<polyline class='base' points='{baseline_points}' />")
    for row in baseline_sorted:
        x = sx(float(row["worst_slack"]))
        y = sy(float(row["total_power_mw"]))
        parts.append(f"<circle class='base-point' cx='{x:.1f}' cy='{y:.1f}' r='4.5' />")
    parts.append(f"<circle class='opt-point' cx='{px:.1f}' cy='{py:.1f}' r='7' />")
    parts.append(f"<text class='tick' x='{px + 8:.1f}' y='{py - 8:.1f}'>optimized</text>")
    parts.append("</svg>")
    write_text(output_path, "\n".join(parts) + "\n")


def run_backend_attempts(rtl_path: Path, target_period: float, run_root: Path) -> Dict[str, object]:
    attempts: List[Dict[str, object]] = []
    run_root.mkdir(parents=True, exist_ok=True)

    for preset in BACKEND_PRESETS:
        attempt_dir = run_root / f"attempt_{preset['name']}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        sdc_path = attempt_dir / "constraint.sdc"
        config_path = attempt_dir / "config.mk"
        synth_log = attempt_dir / "synth.log"
        backend_log = attempt_dir / "backend.log"
        finish_report = attempt_dir / "finish.rpt"

        write_constraint_sdc(sdc_path, target_period)
        write_config_mk(rtl_path, sdc_path, config_path, preset)

        make_prefix = f"cd '{ORFS}' && make DESIGN_CONFIG={to_wsl_path(config_path)} YOSYS_EXE={YOSYS_EXE} OPENROAD_EXE={OPENROAD_EXE}"
        synth = run_wsl_bash(f"{make_prefix} clean_all synth")
        write_text(synth_log, f"STDOUT:\n{synth.stdout}\nSTDERR:\n{synth.stderr}")
        backend = run_wsl_bash(f"{make_prefix} clean_place && {make_prefix}")
        write_text(backend_log, f"STDOUT:\n{backend.stdout}\nSTDERR:\n{backend.stderr}")

        maybe_copy_wsl_file(f"{ORFS}/reports/sky130hd/exp_fixed_point/base/6_finish.rpt", finish_report)
        metrics = parse_finish_report(finish_report)
        point = {
            "target_period_ns": target_period,
            "period_min_ns": metrics["period_min_ns"],
            "wns_ns": metrics["wns"],
            "worst_slack": metrics["worst_slack"],
            "fmax_mhz": metrics["fmax_mhz"],
            "total_power_w": metrics["total_power_w"],
            "total_power_mw": (metrics["total_power_w"] * 1000.0) if metrics["total_power_w"] is not None else None,
            "status": "PASS" if backend.returncode == 0 else "FAIL",
            "attempt_name": preset["name"],
            "attempt_dir": str(attempt_dir),
        }
        write_text(attempt_dir / "metrics.txt", summarize_metrics(point) + "\n")
        attempts.append(point)

    with (run_root / "attempts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "attempt_name",
                "target_period_ns",
                "period_min_ns",
                "wns_ns",
                "worst_slack",
                "fmax_mhz",
                "total_power_w",
                "total_power_mw",
                "status",
                "attempt_dir",
            ],
        )
        writer.writeheader()
        writer.writerows(attempts)

    return max(attempts, key=score_point)


def main() -> None:
    parser = argparse.ArgumentParser(description="Iteratively optimize one RTL until it closes timing at a target period.")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--tb", required=True)
    parser.add_argument("--seed-rtl", required=True)
    parser.add_argument("--baseline-csv")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--target-period", type=float, default=2.0)
    parser.add_argument("--max-rtl-iters", type=int, default=4)
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    tb_path = Path(args.tb).resolve()
    seed_rtl = Path(args.seed_rtl).resolve()
    baseline_csv = Path(args.baseline_csv).resolve() if args.baseline_csv else None
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    baseline_target = load_baseline_target(baseline_csv, args.target_period)
    power_priority = baseline_target is not None

    opt_rtl = out_dir / f"{seed_rtl.stem}_optimized.v"
    best_point: Optional[Dict[str, object]] = None
    best_rtl_snapshot: Optional[Path] = None
    feedback_text = "No prior implementation attempt yet. Start from the seed RTL and close timing."
    iteration_rows: List[Dict[str, object]] = []

    for iteration in range(1, args.max_rtl_iters + 1):
        iter_dir = out_dir / "iterations" / f"iter_{iteration:02d}"
        iter_dir.mkdir(parents=True, exist_ok=True)
        iter_rtl = iter_dir / f"{seed_rtl.stem}_iter_{iteration:02d}.v"
        if iteration == 1:
            shutil.copyfile(seed_rtl, iter_rtl)
        elif best_rtl_snapshot is not None:
            shutil.copyfile(best_rtl_snapshot, iter_rtl)
        else:
            shutil.copyfile(opt_rtl, iter_rtl)

        rc = run_codex(build_prompt(spec_path, seed_rtl, iter_rtl, baseline_csv, args.target_period, feedback_text), REPO_ROOT)
        if rc != 0:
            raise RuntimeError(f"Codex optimization failed in iteration {iteration}.")

        verify_behavioral(iter_rtl, tb_path, iter_dir)
        point = run_backend_attempts(iter_rtl, args.target_period, iter_dir / "backend_attempts")
        point["rtl_path"] = str(iter_rtl)
        point["iteration"] = iteration
        iteration_rows.append(point)
        write_text(iter_dir / "best_attempt.txt", summarize_metrics(point) + f"\nrtl_path={iter_rtl}\n")

        if best_point is None or score_point(point, power_priority=power_priority) > score_point(best_point, power_priority=power_priority):
            best_point = point
            best_rtl_snapshot = iter_rtl
            shutil.copyfile(iter_rtl, opt_rtl)

        if point.get("wns_ns") is not None and float(point["wns_ns"]) >= 0.0:
            best_point = point
            best_rtl_snapshot = iter_rtl
            shutil.copyfile(iter_rtl, opt_rtl)
            if not power_priority:
                break

        if power_priority and baseline_target is not None:
            baseline_power = baseline_target.get("total_power_mw")
            point_power = point.get("total_power_mw")
            if (
                point.get("wns_ns") is not None
                and float(point["wns_ns"]) >= 0.0
                and baseline_power is not None
                and point_power is not None
                and float(point_power) <= float(baseline_power)
            ):
                break

        target_text = ""
        if baseline_target is not None:
            target_text = (
                f"\nBaseline target near {args.target_period:g} ns:\n"
                f"baseline_wns_ns={baseline_target.get('wns_ns')}\n"
                f"baseline_worst_slack={baseline_target.get('worst_slack')}\n"
                f"baseline_total_power_mw={baseline_target.get('total_power_mw')}\n"
                "Do not accept a power increase once timing is already closed unless it materially improves slack."
            )
        feedback_text = (
            "The current RTL still needs improvement.\n"
            f"Best attempt metrics from iteration {iteration}:\n"
            f"{summarize_metrics(point)}"
            f"{target_text}\n"
            "Reduce switching activity and area while preserving behavior."
        )

    if best_point is None:
        raise RuntimeError("No implementation attempt produced metrics.")

    with (out_dir / "iteration_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "iteration",
                "attempt_name",
                "target_period_ns",
                "period_min_ns",
                "wns_ns",
                "worst_slack",
                "fmax_mhz",
                "total_power_w",
                "total_power_mw",
                "status",
                "rtl_path",
                "attempt_dir",
            ],
        )
        writer.writeheader()
        writer.writerows(iteration_rows)

    with (out_dir / "result.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "target_period_ns",
                "period_min_ns",
                "wns_ns",
                "worst_slack",
                "fmax_mhz",
                "total_power_w",
                "total_power_mw",
                "status",
                "attempt_name",
                "iteration",
                "rtl_path",
                "attempt_dir",
            ],
        )
        writer.writeheader()
        writer.writerow(best_point)

    if baseline_csv is not None and baseline_csv.exists():
        with baseline_csv.open("r", encoding="utf-8", newline="") as handle:
            baseline_rows = list(csv.DictReader(handle))
        build_overlay_svg(baseline_rows, best_point, out_dir / "overlay_worst_slack_vs_power.svg")

    write_text(
        out_dir / "summary.txt",
        "\n".join(
            [
                f"seed_rtl={seed_rtl}",
                f"optimized_rtl={opt_rtl}",
                f"best_iteration={best_point.get('iteration')}",
                f"best_attempt={best_point.get('attempt_name')}",
                f"target_period={args.target_period}",
                f"worst_slack={best_point['worst_slack']}",
                f"wns_ns={best_point['wns_ns']}",
                f"power_mw={best_point['total_power_mw']}",
                f"status={best_point['status']}",
                "",
            ]
        ),
    )


if __name__ == "__main__":
    main()
