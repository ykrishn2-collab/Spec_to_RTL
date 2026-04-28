import argparse
import csv
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_codex_orchestrated import parse_spec  # noqa: E402


DISTRO = "Ubuntu"
ORFS = "/home/kyash/OpenROAD-flow-scripts-master/flow"
OPENROAD_EXE = "/home/kyash/OpenROAD/install-clean/bin/openroad"
YOSYS_EXE = "/usr/local/bin/yosys"
TOTAL_POWER_RE = re.compile(r"^Total\s+(?P<internal>[0-9.eE+-]+)\s+(?P<switching>[0-9.eE+-]+)\s+(?P<leakage>[0-9.eE+-]+)\s+(?P<total>[0-9.eE+-]+)")
CRITICAL_PATH_SLACK_RE = re.compile(r"critical path slack\s*\n-+\s*\n(?P<slack>-?[0-9.]+)", re.IGNORECASE)


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


def format_period_tag(period_ns: float) -> str:
    return f"{period_ns:g}".replace(".", "p")


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


def update_clock_period(spec_text: str, period_ns: float) -> str:
    new_text, count = re.subn(
        r"(^\s*clock_period:\s*)([0-9.]+)\s*ns(\s*$)",
        lambda m: f"{m.group(1)}{period_ns:g}ns{m.group(3)}",
        spec_text,
        count=1,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    if count != 1:
        raise ValueError("Could not update clock_period in spec text")
    return new_text


def write_constraint_sdc(problem, out_path: Path) -> None:
    lines = [f"create_clock -name {problem.clock_port} -period {problem.clock_period_ns:g} [get_ports {problem.clock_port}]"]
    for port in problem.ports:
        if port.direction == "input" and port.name != problem.clock_port:
            lines.append(f"set_input_delay 0.5 -clock {problem.clock_port} [get_ports {port.name}]")
    for port in problem.ports:
        if port.direction == "output":
            lines.append(f"set_output_delay 0.5 -clock {problem.clock_port} [get_ports {port.name}]")
    write_text(out_path, "\n".join(lines) + "\n")


def write_config_mk(problem, rtl_path: Path, sdc_path: Path, config_path: Path) -> None:
    text = "\n".join(
        [
            f"export DESIGN_NAME = {problem.top_name}",
            "export PLATFORM = sky130hd",
            "",
            f"export VERILOG_FILES = {to_wsl_path(rtl_path)}",
            f"export SDC_FILE = {to_wsl_path(sdc_path)}",
            "",
            "export DIE_AREA = 0 0 240 240",
            "export CORE_AREA = 30 30 210 210",
            "export PLACE_DENSITY = 0.35",
            "export TNS_END_PERCENT = 100",
            "",
        ]
    )
    write_text(config_path, text)


def parse_finish_report(path: Path) -> Dict[str, Optional[float]]:
    metrics: Dict[str, Optional[float]] = {
        "tns": None,
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
        if stripped.lower().startswith("tns max"):
            metrics["tns"] = float(stripped.split()[-1])
        elif stripped.lower().startswith("worst slack max"):
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


def build_svg(rows: List[Dict[str, object]], output_path: Path) -> None:
    valid = [row for row in rows if row.get("worst_slack") is not None and row.get("total_power_mw") is not None]
    if not valid:
        write_text(output_path, "<svg xmlns='http://www.w3.org/2000/svg' width='960' height='640'></svg>\n")
        return

    width = 960
    height = 640
    left = 90
    right = 40
    top = 40
    bottom = 90
    plot_w = width - left - right
    plot_h = height - top - bottom

    xs = [float(row["worst_slack"]) for row in valid]
    ys = [float(row["total_power_mw"]) for row in valid]
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

    valid.sort(key=lambda row: float(row["worst_slack"]))
    points = " ".join(f"{sx(float(row['worst_slack'])):.1f},{sy(float(row['total_power_mw'])):.1f}" for row in valid)

    parts = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
        "<style>",
        "text { font-family: Arial, sans-serif; fill: #111; }",
        ".axis { stroke: #222; stroke-width: 2; }",
        ".grid { stroke: #d8d8d8; stroke-width: 1; }",
        ".tick { font-size: 12px; }",
        ".label { font-size: 14px; }",
        ".title { font-size: 20px; font-weight: bold; }",
        ".series { fill: none; stroke: #0f766e; stroke-width: 2.5; }",
        ".point { fill: #0f766e; }",
        "</style>",
        f"<rect x='0' y='0' width='{width}' height='{height}' fill='#fcfcf8' />",
        f"<text class='title' x='{left}' y='28'>Fixed RTL Worst Slack vs Power</text>",
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
    parts.append(f"<polyline class='series' points='{points}' />")
    for row in valid:
        x = sx(float(row["worst_slack"]))
        y = sy(float(row["total_power_mw"]))
        label = f"{float(row['target_period_ns']):g}ns"
        parts.append(f"<circle class='point' cx='{x:.1f}' cy='{y:.1f}' r='5.5' />")
        parts.append(f"<text class='tick' x='{x + 8:.1f}' y='{y - 8:.1f}'>{label}</text>")

    parts.append("</svg>")
    write_text(output_path, "\n".join(parts) + "\n")


def run_one(period_ns: float, fixed_rtl_path: Path, base_spec_text: str, out_dir: Path) -> Dict[str, object]:
    period_tag = format_period_tag(period_ns)
    run_dir = out_dir / "runs" / f"period_{period_tag}"
    run_dir.mkdir(parents=True, exist_ok=True)

    spec_path = run_dir / f"{fixed_rtl_path.stem}_{period_tag}.yaml"
    spec_text = update_clock_period(base_spec_text, period_ns)
    write_text(spec_path, spec_text)
    problem = parse_spec(spec_path)

    sdc_path = run_dir / "constraint.sdc"
    config_path = run_dir / "config.mk"
    synth_log = run_dir / "synth.log"
    backend_log = run_dir / "backend.log"
    finish_report = run_dir / "finish.rpt"
    timing_summary = run_dir / "timing_summary.txt"

    write_constraint_sdc(problem, sdc_path)
    write_config_mk(problem, fixed_rtl_path, sdc_path, config_path)

    report_base = f"{ORFS}/reports/sky130hd/{problem.top_name}/base"
    make_prefix = f"cd '{ORFS}' && make DESIGN_CONFIG={to_wsl_path(config_path)} YOSYS_EXE={YOSYS_EXE} OPENROAD_EXE={OPENROAD_EXE}"

    synth = run_wsl_bash(f"{make_prefix} clean_all synth")
    write_text(synth_log, f"STDOUT:\n{synth.stdout}\nSTDERR:\n{synth.stderr}")

    backend = run_wsl_bash(f"{make_prefix} clean_place && {make_prefix}")
    write_text(backend_log, f"STDOUT:\n{backend.stdout}\nSTDERR:\n{backend.stderr}")

    maybe_copy_wsl_file(f"{report_base}/6_finish.rpt", finish_report)
    metrics = parse_finish_report(finish_report)
    write_text(
        timing_summary,
        "\n".join(
            [
                f"wns={metrics['wns']}",
                f"tns={metrics['tns']}",
                f"worst_slack={metrics['worst_slack']}",
                f"period_min={metrics['period_min_ns']}",
                f"target_period={period_ns}",
                "",
            ]
        ),
    )

    return {
        "target_period_ns": period_ns,
        "target_freq_mhz": 1000.0 / period_ns,
        "wns_ns": metrics["wns"],
        "worst_slack": metrics["worst_slack"],
        "period_min_ns": metrics["period_min_ns"],
        "fmax_mhz": metrics["fmax_mhz"],
        "total_power_w": metrics["total_power_w"],
        "total_power_mw": (metrics["total_power_w"] * 1000.0) if metrics["total_power_w"] is not None else None,
        "status": "PASS" if backend.returncode == 0 else "FAIL",
        "run_dir": str(run_dir),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep one fixed RTL across clock periods.")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--rtl", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--periods", nargs="+", required=True, type=float)
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    rtl_path = Path(args.rtl).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    base_spec_text = read_text(spec_path)
    rows = [run_one(period, rtl_path, base_spec_text, out_dir) for period in args.periods]

    csv_path = out_dir / "results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "target_period_ns",
                "target_freq_mhz",
                "wns_ns",
                "worst_slack",
                "period_min_ns",
                "fmax_mhz",
                "total_power_w",
                "total_power_mw",
                "status",
                "run_dir",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    plot_path = out_dir / "worst_slack_vs_power.svg"
    build_svg(rows, plot_path)

    write_text(
        out_dir / "summary.txt",
        "\n".join(
            [
                f"rtl={rtl_path}",
                f"csv={csv_path}",
                f"plot={plot_path}",
                "",
            ]
        ),
    )


if __name__ == "__main__":
    main()
