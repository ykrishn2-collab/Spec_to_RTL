import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


MAX_RTL_ITERS = 5
MAX_SYNTH_ITERS = 5
MAX_BACKEND_ITERS = 1

DEFAULT_WSL_DISTRO = "Ubuntu"
DEFAULT_ORFS = "/home/kyash/OpenROAD-flow-scripts-master/flow"
DEFAULT_OPENROAD_EXE = "/home/kyash/OpenROAD/install-clean/bin/openroad"
DEFAULT_YOSYS_EXE = "/usr/local/bin/yosys"


@dataclass
class PortSpec:
    name: str
    direction: str
    type_text: str


@dataclass
class ProblemSpec:
    top_name: str
    module_signature: str
    clock_period_ns: float
    ports: List[PortSpec]
    clock_port: str
    reset_ports: List[str]


@dataclass
class SynthStrategy:
    name: str
    env: Dict[str, str]


CONFIG_RENDER_CACHE: Dict[str, str] = {}


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


def run_codex_prompt(prompt: str) -> int:
    codex_cmd = find_codex()
    if not codex_cmd:
        print("Could not find Codex CLI.")
        return 1

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
    )
    return result.returncode


def run_codex_capture(prompt: str) -> Tuple[int, str, str]:
    codex_cmd = find_codex()
    if not codex_cmd:
        return 1, "", "Could not find Codex CLI."

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
        capture_output=True,
    )
    return result.returncode, result.stdout, result.stderr


def extract_first_fenced_block(text: str) -> Optional[str]:
    match = re.search(r"```(?:\w+)?\n(.*?)```", text, flags=re.DOTALL)
    if not match:
        return None
    return match.group(1).strip() + "\n"


def extract_first_json_object(text: str) -> Optional[object]:
    fenced = extract_first_fenced_block(text)
    candidates = [fenced, text]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def escape_powershell_single_quoted(text: str) -> str:
    return text.replace("'", "''")


def render_wsl_powershell_command(distro: str, bash_command: str) -> str:
    return f"wsl -d {distro} -- bash -lc '{escape_powershell_single_quoted(bash_command)}'"


def run_command_via_codex(command: str, cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    cwd_text = str(cwd.resolve()) if cwd else str(Path.cwd())
    prompt = f"""
Run exactly one shell command in this repository context and return JSON only.

Requirements:
- Use the current shell environment
- Run exactly this command, with no edits:
{command}
- Working directory: {cwd_text}
- Return JSON only with keys:
  - rc: integer
  - stdout: string
  - stderr: string
""".strip()
    rc, out, err = run_codex_capture(prompt)
    if rc == 0:
        data = extract_first_json_object(out)
        if isinstance(data, dict):
            cmd_rc = data.get("rc")
            cmd_out = data.get("stdout", "")
            cmd_err = data.get("stderr", "")
            if isinstance(cmd_rc, int):
                return cmd_rc, str(cmd_out), str(cmd_err)
    return 1, "", f"Codex command execution failed.\nSTDOUT:\n{out}\nSTDERR:\n{err}"


def plan_command_with_codex(command: str, cwd: Optional[Path] = None) -> str:
    cwd_text = str(cwd.resolve()) if cwd else str(Path.cwd())
    prompt = f"""
You are preparing a shell command for execution.

Requirements:
- Preserve the process and results exactly
- Return JSON only with one key: "command"
- The command must be functionally identical to this command:
{command}
- Do not simplify it, split it, or add wrappers that change behavior
- Working directory: {cwd_text}
""".strip()
    rc, out, err = run_codex_capture(prompt)
    if rc == 0:
        data = extract_first_json_object(out)
        if isinstance(data, dict):
            planned = data.get("command")
            if isinstance(planned, str) and planned.strip():
                return planned.strip()
    return command


def classify_backend_failure_with_codex(log_text: str) -> Optional[Dict[str, str]]:
    prompt = f"""
Classify this OpenROAD/OpenROAD-flow-scripts backend log failure.

Return JSON only with keys:
- failure_kind: one of "placement", "routing", "generic", "unknown"
- rationale: short string

Log excerpt:
{log_text[:20000]}
""".strip()
    rc, out, err = run_codex_capture(prompt)
    if rc == 0:
        data = extract_first_json_object(out)
        if isinstance(data, dict):
            failure_kind = data.get("failure_kind")
            rationale = data.get("rationale", "")
            if failure_kind in {"placement", "routing", "generic", "unknown"}:
                return {"failure_kind": str(failure_kind), "rationale": str(rationale)}
    return None


def parse_finish_timing_with_codex(report_text: str) -> Optional[Dict[str, Optional[float]]]:
    prompt = f"""
Extract final timing metrics from this OpenROAD finish report.

Return JSON only with keys:
- tns
- wns
- worst_slack
- period_min
- fmax

Use numbers when found, otherwise null.

Report excerpt:
{report_text[:24000]}
""".strip()
    rc, out, err = run_codex_capture(prompt)
    if rc == 0:
        data = extract_first_json_object(out)
        if isinstance(data, dict):
            result: Dict[str, Optional[float]] = {}
            for key in ["tns", "wns", "worst_slack", "period_min", "fmax"]:
                value = data.get(key)
                if value is None:
                    result[key] = None
                else:
                    try:
                        result[key] = float(value)
                    except Exception:
                        result[key] = None
            return result
    return None


def run_cmd(cmd: List[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def append_log(log_dir: Path, name: str, text: str):
    write_text(log_dir / name, text)


def parse_simple_yaml_spec(text: str) -> Dict[str, object]:
    lines = text.splitlines()
    top_name = None
    for line in lines:
        if line.strip() and not line.startswith(" "):
            match = re.match(r"([A-Za-z_]\w*):\s*$", line)
            if match:
                top_name = match.group(1)
                break
    if not top_name:
        raise ValueError("Could not find top-level module name in spec")

    clock_match = re.search(r"^\s*clock_period:\s*([0-9.]+)\s*ns\s*$", text, flags=re.MULTILINE | re.IGNORECASE)
    if not clock_match:
        raise ValueError("Could not find clock_period in spec")

    module_sig_match = re.search(
        r"^\s*module_signature:\s*\|\s*\n(?P<body>(?:^(?: {4}|\t).*$\n?)*)",
        text,
        flags=re.MULTILINE,
    )
    if not module_sig_match:
        raise ValueError("Could not find module_signature block in spec")
    module_signature = re.sub(r"^(?: {4}|\t)", "", module_sig_match.group("body"), flags=re.MULTILINE).rstrip()

    ports: List[Dict[str, str]] = []
    port_pattern = re.compile(
        r"^\s*-\s*name:\s*(?P<name>\w+)\s*\n"
        r"^\s*direction:\s*(?P<direction>\w+)\s*\n"
        r"^\s*type:\s*(?P<type>.+?)\s*$",
        flags=re.MULTILINE,
    )
    ports_start = re.search(r"^\s*ports:\s*$", text, flags=re.MULTILINE)
    if not ports_start:
        raise ValueError("Could not find ports section in spec")
    ports_text = text[ports_start.end():]
    for match in port_pattern.finditer(ports_text):
        ports.append(
            {
                "name": match.group("name"),
                "direction": match.group("direction"),
                "type": match.group("type").strip(),
            }
        )
    if not ports:
        raise ValueError("Could not parse ports from spec")

    return {
        top_name: {
            "clock_period": clock_match.group(1) + "ns",
            "module_signature": module_signature,
            "ports": ports,
        }
    }


def parse_spec(spec_path: Path) -> ProblemSpec:
    raw_text = spec_path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(raw_text)
    else:
        data = parse_simple_yaml_spec(raw_text)
    if not isinstance(data, dict) or len(data) != 1:
        raise ValueError(f"Unexpected YAML structure in {spec_path}")

    top_name, body = next(iter(data.items()))
    module_signature = body["module_signature"].strip()
    clock_period_raw = str(body["clock_period"]).strip()
    clock_period_ns = float(clock_period_raw.lower().replace("ns", ""))

    ports = [
        PortSpec(
            name=port["name"],
            direction=port["direction"],
            type_text=str(port["type"]).strip(),
        )
        for port in body["ports"]
    ]

    clock_candidates = [p.name for p in ports if p.name.lower() in {"clk", "clock"}]
    if not clock_candidates:
        raise ValueError(f"Could not infer clock port from {spec_path}")
    clock_port = clock_candidates[0]

    reset_ports = [p.name for p in ports if "rst" in p.name.lower() or "reset" in p.name.lower()]

    return ProblemSpec(
        top_name=top_name,
        module_signature=module_signature,
        clock_period_ns=clock_period_ns,
        ports=ports,
        clock_port=clock_port,
        reset_ports=reset_ports,
    )


def summarize_spec(spec_path: str):
    prompt = f"""
Read {spec_path}.

Summarize briefly:
1. Module name
2. Ports
3. Reset behavior
4. Sequential or combinational logic
5. Expected function

Do not write RTL yet.
Write the summary to logs only by printing it.
""".strip()

    print("\n=== SPEC SUMMARY ===")
    rc = run_codex_prompt(prompt)
    print(f"Codex return code: {rc}")


def generate_initial_rtl(spec_path: str, rtl_path: str, clock_period_ns: Optional[float] = None):
    timing_guidance = ""
    if clock_period_ns is not None:
        timing_guidance = (
            f"- Target implementation clock period is {clock_period_ns} ns on Sky130 HD\n"
            "- Choose the initial microarchitecture with this timing target in mind\n"
        )
    prompt = f"""
Read the hardware specification in {spec_path}.

Generate synthesizable Verilog RTL and write it to {rtl_path}.

Requirements:
- Preserve the EXACT module signature from the spec
- Do NOT add extra ports
- Use synthesizable constructs only
- Follow reset behavior exactly
- Write the initial RTL with timing constraints in mind
- Prefer timing-friendly microarchitecture such as shorter combinational paths, balanced trees, clean staging, and pipelining when compatible with the spec and testbench-visible behavior
- Avoid a timing-naive first version if a more timing-aware structure is obvious
- Prioritize synthesis-effective choices: short logic depth, balanced reductions, controlled fanout, sensible FSM encoding, disciplined datapath widths, and register staging where allowed by the spec
- Avoid long serial arithmetic chains, wide unnecessary mux trees, and oversized intermediate signals if a narrower equivalent implementation is valid
{timing_guidance}
- Only modify {rtl_path}

Do not run simulation.
""".strip()

    print("\n=== GENERATE INITIAL RTL ===")
    rc = run_codex_prompt(prompt)
    print(f"Codex return code: {rc}")


def fix_compile_errors(spec_path: str, rtl_path: str, compile_log: str):
    prompt = f"""
The RTL file {rtl_path} failed compilation.

Fix only {rtl_path}.

Requirements:
- Preserve the EXACT module signature from {spec_path}
- Do NOT add extra ports
- Do NOT modify the testbench
- Use synthesizable constructs only

Compiler log:
{compile_log}
""".strip()

    print("\n=== FIX COMPILE ERRORS ===")
    rc = run_codex_prompt(prompt)
    print(f"Codex return code: {rc}")


def fix_simulation_errors(spec_path: str, rtl_path: str, sim_log: str):
    prompt = f"""
The RTL file {rtl_path} compiles but fails simulation.

Fix only {rtl_path}.

Requirements:
- Preserve the EXACT module signature from {spec_path}
- Do NOT add extra ports
- Do NOT modify the testbench
- Use synthesizable constructs only

Simulation output:
{sim_log}
""".strip()

    print("\n=== FIX SIMULATION ERRORS ===")
    rc = run_codex_prompt(prompt)
    print(f"Codex return code: {rc}")


def fix_synthesis_errors(spec_path: str, rtl_path: str, synth_log: str):
    prompt = f"""
The RTL file {rtl_path} passed behavioral simulation but failed synthesis/OpenROAD frontend.

Fix only {rtl_path}.

Requirements:
- Preserve the EXACT module signature from {spec_path}
- Do NOT add extra ports
- Do NOT modify the testbench
- Use synthesizable constructs only
- Keep the design compatible with Sky130 HD synthesis

Synthesis/OpenROAD log:
{synth_log}
""".strip()

    print("\n=== FIX SYNTHESIS ERRORS ===")
    rc = run_codex_prompt(prompt)
    print(f"Codex return code: {rc}")


def fix_gls_errors(spec_path: str, rtl_path: str, gls_log: str):
    prompt = f"""
The RTL file {rtl_path} passed behavioral simulation, but the fresh gate-level netlist failed dynamic simulation.

Fix only {rtl_path}.

Requirements:
- Preserve the EXACT module signature from {spec_path}
- Do NOT add extra ports
- Do NOT modify the testbench
- Use synthesizable constructs only
- The fix must remove RTL-to-gate mismatches cleanly after resynthesis

Gate-level simulation output:
{gls_log}
""".strip()

    print("\n=== FIX GLS ERRORS ===")
    rc = run_codex_prompt(prompt)
    print(f"Codex return code: {rc}")


def fix_timing_errors(spec_path: str, rtl_path: str, timing_log: str):
    prompt = f"""
The RTL file {rtl_path} passes behavioral simulation and gate-level simulation, but the final OpenROAD implementation misses timing.

Fix only {rtl_path}.

Requirements:
- Preserve the EXACT module signature from {spec_path}
- Do NOT add extra ports
- Do NOT modify the testbench
- Use synthesizable constructs only
- Improve microarchitecture and timing for Sky130 HD
- Prefer synthesis-effective timing fixes in this order when applicable:
  1. Reduce combinational depth
  2. Add or rebalance staging/pipelining if compatible with the spec and testbench-visible behavior
  3. Replace serial arithmetic with balanced trees
  4. Reduce fanout by restructuring or register duplication when valid
  5. Tighten datapath widths to only what is required
  6. Use a more timing-friendly FSM/output structure
- Prefer synchronous reset style if the spec allows it and it improves timing
- Avoid blind rewrites that preserve functionality but make the critical path deeper or control logic wider
- The updated RTL must still match the existing testbench behavior after regeneration and resynthesis

Timing report excerpts:
{timing_log}
""".strip()

    print("\n=== FIX TIMING ERRORS ===")
    rc = run_codex_prompt(prompt)
    print(f"Codex return code: {rc}")


def detect_sim_pass(stdout: str, stderr: str) -> bool:
    text = f"{stdout}\n{stderr}".upper()
    return "PASS" in text and "FAIL" not in text


def compile_rtl(rtl_path: Path, tb_path: Path, sim_out: Path) -> Tuple[int, str, str]:
    return run_cmd(["iverilog", "-g2012", "-o", str(sim_out), str(rtl_path), str(tb_path)])


def run_sim(sim_out: Path) -> Tuple[int, str, str]:
    return run_cmd(["vvp", str(sim_out)])


def try_behavioral_loop(
    spec_path: Path,
    tb_path: Path,
    rtl_path: Path,
    log_dir: Path,
    reuse_existing_rtl: bool,
) -> bool:
    log_dir.mkdir(parents=True, exist_ok=True)
    summarize_spec(str(spec_path))
    problem = parse_spec(spec_path)
    if not reuse_existing_rtl:
        generate_initial_rtl(str(spec_path), str(rtl_path), problem.clock_period_ns)

    if not rtl_path.exists():
        print(f"ERROR: RTL not created: {rtl_path}")
        return False

    sim_out = log_dir / "sim.out"

    for idx in range(MAX_RTL_ITERS):
        print(f"\n===== RTL ITERATION {idx} =====")
        rc, out, err = compile_rtl(rtl_path, tb_path, sim_out)
        compile_log = f"STDOUT:\n{out}\nSTDERR:\n{err}"
        append_log(log_dir, f"compile_{idx}.log", compile_log)
        if rc != 0:
            print("Compile failed.")
            fix_compile_errors(str(spec_path), str(rtl_path), compile_log)
            continue

        rc, out, err = run_sim(sim_out)
        sim_log = f"STDOUT:\n{out}\nSTDERR:\n{err}"
        append_log(log_dir, f"sim_{idx}.log", sim_log)
        if rc == 0 and detect_sim_pass(out, err):
            write_text(log_dir / "behavioral_status.txt", "PASS\n")
            return True

        print("Behavioral simulation failed.")
        fix_simulation_errors(str(spec_path), str(rtl_path), sim_log)

    write_text(log_dir / "behavioral_status.txt", "FAIL\n")
    return False


def find_problem_stem(spec_path: Path) -> str:
    match = re.match(r"p\d+", spec_path.stem, re.IGNORECASE)
    if match:
        return match.group(0).lower()
    return spec_path.stem.lower()


def discover_wsl_env() -> Dict[str, str]:
    return {
        "distro": DEFAULT_WSL_DISTRO,
        "orfs": DEFAULT_ORFS,
        "openroad_exe": DEFAULT_OPENROAD_EXE,
        "yosys_exe": DEFAULT_YOSYS_EXE,
    }


def run_wsl_bash(command: str) -> Tuple[int, str, str]:
    return run_cmd(["wsl", "-d", DEFAULT_WSL_DISTRO, "--", "bash", "-lc", command])


def ensure_openroad_models(model_root: Path, log_dir: Path) -> bool:
    marker = model_root / "models" / "udp_dff_nsr" / "sky130_fd_sc_hd__udp_dff_nsr.v"
    if marker.exists():
        return True

    clone_cmd = (
        "git clone https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd.git "
        f"'{str(model_root).replace(chr(92), '/')}'"
    )
    rc, out, err = run_cmd(["powershell", "-Command", clone_cmd])
    append_log(log_dir, "model_clone.log", f"STDOUT:\n{out}\nSTDERR:\n{err}")
    return rc == 0 and marker.exists()


def choose_initial_die(problem: ProblemSpec, problem_stem: str, body_area_hint: int = 240) -> Tuple[int, int]:
    die = max(240, body_area_hint)
    if problem_stem == "p9" or problem.top_name == "fir_filter":
        die = max(die, 420)
    elif problem_stem == "p5" or problem.top_name == "dot_product":
        die = max(die, 288)
    margin = 30
    return die, margin


def get_synth_strategies(problem: ProblemSpec) -> List[SynthStrategy]:
    top = problem.top_name
    prompt = f"""
You are preparing a synthesis strategy plan for OpenROAD-flow-scripts/Yosys on Sky130 HD.

Return JSON only. The result must be a JSON array of objects with:
- "name": string
- "env": object of string keys to string values

Keep the process exactly aligned with this baseline strategy order unless there is a compelling reason not to:
1. baseline_speed => {{}}
2. retime_top => {{"SYNTH_RETIME_MODULES": "{top}"}}
3. insbuf_retime => {{"SYNTH_RETIME_MODULES": "{top}", "SYNTH_INSBUF": "1"}}
4. hier_opt => {{"SYNTH_OPT_HIER": "1"}}
5. hier_opt_retime => {{"SYNTH_OPT_HIER": "1", "SYNTH_RETIME_MODULES": "{top}"}}

Design context:
- top module: {problem.top_name}
- target clock: {problem.clock_period_ns} ns

Return only the JSON array.
""".strip()
    rc, out, err = run_codex_capture(prompt)
    if rc == 0:
        data = extract_first_json_object(out)
        if isinstance(data, list) and data:
            strategies: List[SynthStrategy] = []
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                env = entry.get("env", {})
                if isinstance(name, str) and isinstance(env, dict):
                    env_str = {str(k): str(v) for k, v in env.items()}
                    strategies.append(SynthStrategy(name, env_str))
            if strategies:
                return strategies

    return [
        SynthStrategy("baseline_speed", {}),
        SynthStrategy("retime_top", {"SYNTH_RETIME_MODULES": top}),
        SynthStrategy("insbuf_retime", {"SYNTH_RETIME_MODULES": top, "SYNTH_INSBUF": "1"}),
        SynthStrategy("hier_opt", {"SYNTH_OPT_HIER": "1"}),
        SynthStrategy("hier_opt_retime", {"SYNTH_OPT_HIER": "1", "SYNTH_RETIME_MODULES": top}),
    ]


def build_safe_sdc(problem: ProblemSpec) -> str:
    lines = [f"create_clock -name {problem.clock_port} -period {problem.clock_period_ns} [get_ports {problem.clock_port}]"]
    for port in problem.ports:
        if port.direction == "input" and port.name != problem.clock_port:
            lines.append(f"set_input_delay 0.5 -clock {problem.clock_port} [get_ports {port.name}]")
    for port in problem.ports:
        if port.direction == "output":
            lines.append(f"set_output_delay 0.5 -clock {problem.clock_port} [get_ports {port.name}]")
    return "\n".join(lines) + "\n"


def sanitize_sdc_for_openroad(text: str, problem: ProblemSpec) -> str:
    normalized = text.replace("\r\n", "\n")
    unsupported_tokens = (
        "remove_from_collection",
        "[all_inputs]",
        "[all_outputs]",
        "[all_clocks]",
        "get_clocks",
    )
    if any(token in normalized for token in unsupported_tokens):
        return build_safe_sdc(problem)

    stripped_lines = [line.rstrip() for line in normalized.splitlines() if line.strip()]
    if not stripped_lines:
        return build_safe_sdc(problem)
    if not any("create_clock" in line for line in stripped_lines):
        return build_safe_sdc(problem)
    return "\n".join(stripped_lines) + "\n"


def synth_log_has_sdc_error(log_text: str) -> bool:
    lowered = log_text.lower()
    if "read_sdc" not in lowered:
        return False
    sdc_markers = (
        ".sdc",
        "invalid command name",
        "error:",
        "syntax error",
        "unknown command",
    )
    return any(marker in lowered for marker in sdc_markers)


def write_constraint_sdc(problem: ProblemSpec, out_path: Path):
    port_summary = "\n".join(
        f"- {port.direction} {port.name} : {port.type_text}"
        for port in problem.ports
    )
    prompt = f"""
Write an SDC file for this design.

Requirements:
- Use exactly one clock on port {problem.clock_port}
- Clock period is {problem.clock_period_ns} ns
- Set input delay of 0.5 on every non-clock input
- Set output delay of 0.5 on every output
- Preserve the current process and results, so keep the constraints simple and aligned with this policy

Ports:
{port_summary}

Return only one fenced ```tcl``` block containing the SDC text.
""".strip()
    rc, out, err = run_codex_capture(prompt)
    if rc == 0:
        block = extract_first_fenced_block(out)
        if block:
            write_text(out_path, sanitize_sdc_for_openroad(block, problem))
            return

    write_text(out_path, build_safe_sdc(problem))


def write_config_mk(
    problem: ProblemSpec,
    rtl_path: Path,
    sdc_path: Path,
    config_path: Path,
    die_size: int,
    margin: int,
    place_density: float = 0.35,
    tns_end_percent: int = 100,
    extra_env: Optional[Dict[str, str]] = None,
):
    core_ll = margin
    core_ur = die_size - margin
    extra_env = extra_env or {}
    cache_key = json.dumps(
        {
            "design_name": problem.top_name,
            "rtl": to_wsl_path(rtl_path),
            "sdc": to_wsl_path(sdc_path),
            "die": die_size,
            "margin": margin,
            "density": round(place_density, 2),
            "tns_end_percent": tns_end_percent,
            "extra_env": extra_env,
        },
        sort_keys=True,
    )
    if cache_key in CONFIG_RENDER_CACHE:
        write_text(config_path, CONFIG_RENDER_CACHE[cache_key])
        return

    extra_lines_text = "\n".join(f"- {k} = {v}" for k, v in extra_env.items()) or "- none"
    prompt = f"""
Write an OpenROAD-flow-scripts config.mk file.

Requirements:
- Preserve the current process and results
- Use these exact values
- Return only one fenced ```makefile``` block

Values:
- DESIGN_NAME = {problem.top_name}
- PLATFORM = sky130hd
- VERILOG_FILES = {to_wsl_path(rtl_path)}
- SDC_FILE = {to_wsl_path(sdc_path)}
- DIE_AREA = 0 0 {die_size} {die_size}
- CORE_AREA = {core_ll} {core_ll} {core_ur} {core_ur}
- PLACE_DENSITY = {place_density:.2f}
- TNS_END_PERCENT = {tns_end_percent}

Additional exports:
{extra_lines_text}
""".strip()
    rc, out, err = run_codex_capture(prompt)
    if rc == 0:
        block = extract_first_fenced_block(out)
        if block:
            CONFIG_RENDER_CACHE[cache_key] = block
            write_text(config_path, block)
            return

    text = "\n".join(
        [
            f"export DESIGN_NAME = {problem.top_name}",
            "export PLATFORM = sky130hd",
            "",
            f"export VERILOG_FILES = {to_wsl_path(rtl_path)}",
            f"export SDC_FILE = {to_wsl_path(sdc_path)}",
            "",
            f"export DIE_AREA = 0 0 {die_size} {die_size}",
            f"export CORE_AREA = {core_ll} {core_ll} {core_ur} {core_ur}",
            f"export PLACE_DENSITY = {place_density:.2f}",
            f"export TNS_END_PERCENT = {tns_end_percent}",
            "",
        ]
    )
    if extra_env:
        extra_lines = [f"export {key} = {value}" for key, value in extra_env.items()]
        text = text + "\n" + "\n".join(extra_lines) + "\n"
    CONFIG_RENDER_CACHE[cache_key] = text
    write_text(config_path, text)


def to_wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix().split(":", 1)[1]
    return f"/mnt/{drive}{rest}"


def copy_if_exists(src: str, dst: Path):
    rc, out, err = run_wsl_bash(f"test -f '{src}' && cat '{src}' > '{to_wsl_path(dst)}'")
    if rc != 0:
        raise RuntimeError(f"Failed copying {src} -> {dst}\nSTDOUT:\n{out}\nSTDERR:\n{err}")


def read_wsl_file(path: str) -> str:
    rc, out, err = run_wsl_bash(f"cat '{path}'")
    if rc != 0:
        raise RuntimeError(f"Failed reading {path}\nSTDOUT:\n{out}\nSTDERR:\n{err}")
    return out


def extract_module_name(signature: str) -> str:
    match = re.search(r"\bmodule\s+([A-Za-z_]\w*)", signature)
    if not match:
        raise ValueError("Could not extract module name from module signature")
    return match.group(1)


def parse_type_bits(type_text: str) -> Tuple[bool, List[str]]:
    signed = " signed " in f" {type_text} "
    dims = re.findall(r"\[([^\]]+)\]", type_text)
    return signed, dims


def range_to_width_expr(dim_text: str) -> str:
    match = re.fullmatch(r"\s*(.+?)\s*-\s*1\s*:\s*0\s*", dim_text)
    if match:
        return f"({match.group(1).strip()})"
    msb_lsb = re.fullmatch(r"\s*(.+?)\s*:\s*(.+?)\s*", dim_text)
    if msb_lsb:
        msb = msb_lsb.group(1).strip()
        lsb = msb_lsb.group(2).strip()
        return f"(({msb})-({lsb})+1)"
    raise ValueError(f"Unsupported packed range: [{dim_text}]")


def build_flat_wire_decl(port: PortSpec) -> Optional[Tuple[str, str]]:
    signed, dims = parse_type_bits(port.type_text)
    if len(dims) <= 1:
        return None
    width_exprs = [range_to_width_expr(dim) for dim in dims]
    flat_expr = "*".join(width_exprs)
    signed_kw = " signed" if signed else ""
    return (f"wire{signed_kw} [{flat_expr}-1:0] {port.name}_flat;", port.name)


def wrapper_expr_for_port(port: PortSpec) -> Tuple[Optional[str], List[str], str]:
    flat_decl = build_flat_wire_decl(port)
    if flat_decl is None:
        return None, [], port.name

    decl, base_name = flat_decl
    assigns: List[str] = []
    if port.direction == "input":
        assigns.append(f"assign {base_name}_flat = {base_name};")
    else:
        assigns.append(f"assign {base_name} = {base_name}_flat;")
    return decl, assigns, f"{base_name}_flat"


def generate_gls_wrapper(problem: ProblemSpec, wrapper_path: Path, renamed_top: str):
    lines: List[str] = []
    lines.append(problem.module_signature)
    lines.append("")

    flat_decls: List[str] = []
    assigns: List[str] = []
    connections: List[str] = []

    for port in problem.ports:
        decl, new_assigns, conn_name = wrapper_expr_for_port(port)
        if decl:
            flat_decls.append(f"    {decl}")
            assigns.extend([f"    {line}" for line in new_assigns])
        connections.append(f"        .{port.name}({conn_name})")

    if flat_decls:
        lines.extend(flat_decls)
        lines.append("")
    if assigns:
        lines.extend(assigns)
        lines.append("")

    lines.append(f"    {renamed_top} dut (")
    lines.append(",\n".join(connections))
    lines.append("    );")
    lines.append("")
    lines.append("endmodule")
    lines.append("")

    write_text(wrapper_path, "\n".join(lines))


def rename_netlist_top(src: Path, dst: Path, old_top: str, new_top: str):
    text = read_text(src)
    text, count = re.subn(rf"\bmodule\s+{re.escape(old_top)}\b", f"module {new_top}", text, count=1)
    if count != 1:
        raise RuntimeError(f"Could not rename module {old_top} in {src}")
    write_text(dst, text)


def build_gls_filelist(netlist_path: Path, model_root: Path, out_file: Path):
    text = read_text(netlist_path)
    mods = sorted(set(re.findall(r"^\s*(sky130_fd_sc_hd__\S+)\s+\S+\s*\(", text, flags=re.MULTILINE)))
    udp_files = sorted(
        p for p in model_root.rglob("*.v")
        if "/models/" in p.as_posix()
        and not re.search(r"\.(tb|blackbox|symbol)\.v$", p.name)
    )

    wrapper_files: List[Path] = []
    for mod in mods:
        cell = re.sub(r"^sky130_fd_sc_hd__", "", mod)
        cell_base = re.sub(r"_\d+$", "", cell)
        candidate = model_root / "cells" / cell_base / f"{mod}.v"
        if not candidate.exists():
            raise RuntimeError(f"Missing Sky130 model wrapper for {mod}: {candidate}")
        wrapper_files.append(candidate)

    filelist = [p.as_posix() for p in udp_files] + [p.as_posix() for p in sorted(set(wrapper_files))]
    write_text(out_file, "\n".join(filelist) + "\n")


def detect_tb_top(tb_path: Path) -> str:
    text = read_text(tb_path)
    match = re.search(r"\bmodule\s+([A-Za-z_]\w*)\b", text)
    if not match:
        raise ValueError(f"Could not detect testbench top module in {tb_path}")
    return match.group(1)


def compile_gls(
    filelist_path: Path,
    model_root: Path,
    renamed_netlist: Path,
    wrapper_path: Path,
    tb_path: Path,
    output_path: Path,
) -> Tuple[int, str, str]:
    tb_top = detect_tb_top(tb_path)
    cmd = [
        "iverilog",
        "-g2012",
        "-grelative-include",
        "-DFUNCTIONAL",
        "-DUNIT_DELAY=",
        "-I",
        str(model_root),
        "-s",
        tb_top,
        "-o",
        str(output_path),
        "-c",
        str(filelist_path),
        str(renamed_netlist),
        str(wrapper_path),
        str(tb_path),
    ]
    return run_cmd(cmd)


def detect_backend_failure(log_text: str) -> str:
    codex_result = classify_backend_failure_with_codex(log_text)
    if codex_result is not None:
        return codex_result["failure_kind"]
    lowered = log_text.lower()
    if "gpl-0301" in lowered or "global placement failed" in lowered:
        return "placement"
    if "detailed placement failed" in lowered:
        return "placement"
    if "routing congestion" in lowered or "global route failed" in lowered:
        return "routing"
    if "error:" in lowered or "failed" in lowered:
        return "generic"
    return "unknown"


def write_backend_failure_analysis(log_dir: Path, stem: str, log_text: str):
    codex_result = classify_backend_failure_with_codex(log_text)
    if codex_result is None:
        return
    write_text(
        log_dir / f"{stem}_analysis.txt",
        "\n".join(
            [
                f"failure_kind={codex_result['failure_kind']}",
                f"rationale={codex_result['rationale']}",
                "",
            ]
        ),
    )


def write_finish_analysis(log_dir: Path, stem: str, report_text: str):
    codex_result = parse_finish_timing_with_codex(report_text)
    if codex_result is None:
        return
    write_text(
        log_dir / f"{stem}_analysis.txt",
        "\n".join(
            [
                f"tns={codex_result.get('tns')}",
                f"wns={codex_result.get('wns')}",
                f"worst_slack={codex_result.get('worst_slack')}",
                f"period_min={codex_result.get('period_min')}",
                f"fmax={codex_result.get('fmax')}",
                "",
            ]
        ),
    )


def scale_floorplan(die_size: int, margin: int) -> Tuple[int, int]:
    new_die = int(die_size * 1.2)
    new_margin = max(margin, 30)
    return new_die, new_margin


def run_synth(env: Dict[str, str], config_path: Path, log_path: Path) -> Tuple[bool, str]:
    bash_cmd = (
        f"cd '{env['orfs']}' && "
        f"make DESIGN_CONFIG={to_wsl_path(config_path)} "
        f"YOSYS_EXE={env['yosys_exe']} OPENROAD_EXE={env['openroad_exe']} clean_all synth"
    )
    command = render_wsl_powershell_command(env["distro"], bash_cmd)
    planned_command = plan_command_with_codex(command, cwd=Path.cwd())
    rc, out, err = run_wsl_bash(bash_cmd)
    append_log(
        log_path.parent,
        log_path.name,
        f"PLANNED_COMMAND:\n{planned_command}\n\nEXECUTED_COMMAND:\n{command}\n\nSTDOUT:\n{out}\nSTDERR:\n{err}",
    )
    return rc == 0, f"STDOUT:\n{out}\nSTDERR:\n{err}"


def run_backend(env: Dict[str, str], config_path: Path, log_path: Path) -> Tuple[bool, str]:
    bash_cmd = (
        f"cd '{env['orfs']}' && "
        f"make DESIGN_CONFIG={to_wsl_path(config_path)} "
        f"YOSYS_EXE={env['yosys_exe']} OPENROAD_EXE={env['openroad_exe']} clean_place && "
        f"make DESIGN_CONFIG={to_wsl_path(config_path)} "
        f"YOSYS_EXE={env['yosys_exe']} OPENROAD_EXE={env['openroad_exe']}"
    )
    command = render_wsl_powershell_command(env["distro"], bash_cmd)
    planned_command = plan_command_with_codex(command, cwd=Path.cwd())
    rc, out, err = run_wsl_bash(bash_cmd)
    log_text = f"PLANNED_COMMAND:\n{planned_command}\n\nEXECUTED_COMMAND:\n{command}\n\nSTDOUT:\n{out}\nSTDERR:\n{err}"
    append_log(log_path.parent, log_path.name, log_text)
    return rc == 0, log_text


def collect_synth_artifacts(problem: ProblemSpec, out_dir: Path):
    base = f"{DEFAULT_ORFS}/results/sky130hd/{problem.top_name}/base"
    copies = {
        f"{base}/1_2_yosys.v": out_dir / "gate_synth_raw.v",
    }
    for src, dst in copies.items():
        copy_if_exists(src, dst)


def collect_final_artifacts(problem: ProblemSpec, out_dir: Path, artifact_prefix: str):
    base = f"{DEFAULT_ORFS}/results/sky130hd/{problem.top_name}/base"
    copies = {
        f"{base}/6_final.v": out_dir / "closed_raw.v",
        f"{base}/6_final.def": out_dir / f"{artifact_prefix}.def",
        f"{base}/6_final.gds": out_dir / f"{artifact_prefix}.gds",
        f"{base}/6_final.sdc": out_dir / f"{artifact_prefix}.sdc",
        f"{base}/6_final.spef": out_dir / f"{artifact_prefix}.spef",
    }
    for src, dst in copies.items():
        copy_if_exists(src, dst)


def collect_final_reports(problem: ProblemSpec, log_dir: Path, suffix: str = ""):
    base = f"{DEFAULT_ORFS}/reports/sky130hd/{problem.top_name}/base"
    reports = {
        f"{base}/4_cts_final.rpt": log_dir / f"cts_final{suffix}.rpt",
        f"{base}/5_global_route.rpt": log_dir / f"global_route{suffix}.rpt",
        f"{base}/6_finish.rpt": log_dir / f"finish{suffix}.rpt",
    }
    for src, dst in reports.items():
        copy_if_exists(src, dst)


def parse_finish_timing(report_text: str) -> Dict[str, Optional[float]]:
    codex_result = parse_finish_timing_with_codex(report_text)
    if codex_result is not None:
        return codex_result

    def extract(pattern: str) -> Optional[float]:
        match = re.search(pattern, report_text, flags=re.IGNORECASE)
        if not match:
            return None
        return float(match.group(1))

    report_wns = extract(r"wns\s+max\s+(-?[0-9.]+)")
    critical_path_slack = extract(r"critical path slack\s*\n-+\s*\n(-?[0-9.]+)")

    return {
        "tns": extract(r"tns\s+max\s+(-?[0-9.]+)"),
        "wns": critical_path_slack if critical_path_slack is not None else report_wns,
        "report_wns": report_wns,
        "worst_slack": extract(r"worst slack\s+max\s+(-?[0-9.]+)"),
        "critical_path_slack": critical_path_slack,
        "period_min": extract(r"period_min\s*=\s*([0-9.]+)"),
        "fmax": extract(r"fmax\s*=\s*([0-9.]+)"),
    }


def timing_is_closed(metrics: Dict[str, Optional[float]], target_period_ns: float) -> bool:
    wns = metrics.get("wns")
    period_min = metrics.get("period_min")
    if wns is None:
        return False
    if wns < 0:
        return False
    if period_min is not None and period_min > target_period_ns + 1e-9:
        return False
    return True


def metrics_score(metrics: Dict[str, Optional[float]], target_period_ns: float) -> Tuple[float, float]:
    wns = metrics.get("wns")
    period_min = metrics.get("period_min")
    wns_score = wns if wns is not None else -1e9
    if period_min is None:
        period_score = -1e9
    else:
        period_score = -abs(period_min - target_period_ns)
    return (wns_score, period_score)


def is_better_timing(
    candidate: Dict[str, Optional[float]],
    incumbent: Optional[Dict[str, Optional[float]]],
    target_period_ns: float,
) -> bool:
    if incumbent is None:
        return True
    return metrics_score(candidate, target_period_ns) > metrics_score(incumbent, target_period_ns)


def scale_floorplan_from_timing(
    die_size: int,
    margin: int,
    metrics: Dict[str, Optional[float]],
    target_period_ns: float,
) -> Tuple[int, int]:
    period_min = metrics.get("period_min")
    wns = metrics.get("wns")
    if period_min is not None and target_period_ns > 0:
        growth = max(math.sqrt(period_min / target_period_ns) * 1.08, 1.08)
    elif wns is not None and wns < 0 and target_period_ns > 0:
        growth = max(math.sqrt((target_period_ns - wns) / target_period_ns) * 1.08, 1.08)
    else:
        growth = 1.12
    new_die = int(math.ceil((die_size * growth) / 5.0) * 5)
    if new_die <= die_size:
        new_die = die_size + 40
    return new_die, max(margin, 30)


def adjust_backend_knobs_on_failure(
    die_size: int,
    margin: int,
    place_density: float,
    failure_kind: str,
) -> Tuple[int, int, float]:
    new_die, new_margin = die_size, margin
    new_density = place_density
    if failure_kind in {"placement", "routing", "generic"}:
        if place_density > 0.26:
            new_density = max(0.24, round(place_density - 0.04, 2))
        else:
            new_die, new_margin = scale_floorplan(die_size, margin)
            new_density = max(0.22, round(place_density - 0.02, 2))
    return new_die, new_margin, new_density


def run_full_flow(
    spec_path: Path,
    tb_path: Path,
    rtl_path: Path,
    logs_dir: Path,
    work_root: Path,
) -> bool:
    problem = parse_spec(spec_path)
    env = discover_wsl_env()
    problem_stem = find_problem_stem(spec_path)
    flow_dir = work_root / problem_stem
    out_dir = flow_dir / "out"
    gls_dir = flow_dir / "gls"
    model_root = flow_dir / "sky130_fd_sc_hd_models"
    config_path = flow_dir / "config.mk"
    sdc_path = flow_dir / "constraint.sdc"
    flow_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    gls_dir.mkdir(parents=True, exist_ok=True)

    if not ensure_openroad_models(model_root, logs_dir):
        print("Sky130 model download/check failed.")
        return False

    die_size, margin = choose_initial_die(problem, problem_stem)
    write_constraint_sdc(problem, sdc_path)
    best_metrics: Optional[Dict[str, Optional[float]]] = None
    best_rtl_path = logs_dir / "best_rtl.v"
    best_timing_path = logs_dir / "best_timing_summary.txt"
    synth_strategies = get_synth_strategies(problem)

    renamed_top = f"{problem.top_name}_gate"
    wrapper_path = gls_dir / f"{problem.top_name}_gls_wrapper.v"
    generate_gls_wrapper(problem, wrapper_path, renamed_top)

    for full_iter in range(MAX_SYNTH_ITERS):
        frozen_rtl = logs_dir / f"rtl_snapshot_{full_iter}.v"
        shutil.copyfile(rtl_path, frozen_rtl)
        last_timing_excerpt = ""
        rtl_iteration_closed = False

        for synth_iter, synth_strategy in enumerate(synth_strategies):
            shutil.copyfile(frozen_rtl, rtl_path)
            write_text(
                logs_dir / f"synth_strategy_{full_iter}_{synth_iter}.txt",
                "\n".join(
                    [
                        f"name={synth_strategy.name}",
                        *[f"{key}={value}" for key, value in synth_strategy.env.items()],
                        "",
                    ]
                ),
            )
            write_config_mk(
                problem,
                rtl_path,
                sdc_path,
                config_path,
                die_size,
                margin,
                extra_env=synth_strategy.env,
            )
            synth_log = logs_dir / f"synth_{full_iter}_{synth_iter}.log"
            synth_ok, synth_text = run_synth(env, config_path, synth_log)
            if not synth_ok:
                if synth_log_has_sdc_error(synth_text):
                    write_text(sdc_path, build_safe_sdc(problem))
                    append_log(
                        logs_dir,
                        f"sdc_repair_{full_iter}_{synth_iter}.log",
                        "Detected OpenROAD SDC parse failure during synth. Rewrote constraint.sdc with deterministic OpenROAD-safe constraints.\n",
                    )
                    write_config_mk(
                        problem,
                        rtl_path,
                        sdc_path,
                        config_path,
                        die_size,
                        margin,
                        extra_env=synth_strategy.env,
                    )
                continue
            write_text(logs_dir / "synth_status.txt", "PASS\n")

            collect_synth_artifacts(problem, out_dir)
            synth_netlist = out_dir / f"{problem_stem}_gate_synth.v"
            shutil.copyfile(out_dir / "gate_synth_raw.v", synth_netlist)

            renamed_synth = gls_dir / f"{problem_stem}_gate_synth_renamed.v"
            synth_filelist = gls_dir / "sky130_wrappers_synth_only.f"
            rename_netlist_top(synth_netlist, renamed_synth, problem.top_name, renamed_top)
            build_gls_filelist(renamed_synth, model_root, synth_filelist)

            synth_gls_out = gls_dir / f"{problem_stem}_gate_synth_clean.out"
            rc, out, err = compile_gls(synth_filelist, model_root, renamed_synth, wrapper_path, tb_path, synth_gls_out)
            append_log(logs_dir, "gls_synth_compile.log", f"STDOUT:\n{out}\nSTDERR:\n{err}")
            if rc != 0:
                continue

            rc, out, err = run_sim(synth_gls_out)
            append_log(logs_dir, "gls_synth_run.log", f"STDOUT:\n{out}\nSTDERR:\n{err}")
            if rc != 0 or not detect_sim_pass(out, err):
                continue
            write_text(logs_dir / "gls_synth_status.txt", "PASS\n")

            backend_ok = False
            backend_timing_closed = False
            backend_die = die_size
            backend_margin = margin
            backend_place_density = 0.35
            backend_tns_end_percent = 100
            for backend_iter in range(MAX_BACKEND_ITERS):
                write_config_mk(
                    problem,
                    rtl_path,
                    sdc_path,
                    config_path,
                    backend_die,
                    backend_margin,
                    backend_place_density,
                    backend_tns_end_percent,
                    synth_strategy.env,
                )
                write_text(
                    logs_dir / f"backend_{full_iter}_{synth_iter}_{backend_iter}_strategy.txt",
                    "\n".join(
                        [
                            f"die_size={backend_die}",
                            f"margin={backend_margin}",
                            f"place_density={backend_place_density:.2f}",
                            f"tns_end_percent={backend_tns_end_percent}",
                            f"synth_strategy={synth_strategy.name}",
                            "",
                        ]
                    ),
                )
                backend_log = logs_dir / f"backend_{full_iter}_{synth_iter}_{backend_iter}.log"
                ok, backend_text = run_backend(env, config_path, backend_log)
                if not ok:
                    write_backend_failure_analysis(
                        logs_dir,
                        f"backend_{full_iter}_{synth_iter}_{backend_iter}",
                        backend_text,
                    )
                    failure_kind = detect_backend_failure(backend_text)
                    if failure_kind in {"placement", "routing", "generic"}:
                        backend_die, backend_margin, backend_place_density = adjust_backend_knobs_on_failure(
                            backend_die,
                            backend_margin,
                            backend_place_density,
                            failure_kind,
                        )
                        continue
                    break

                backend_ok = True
                die_size, margin = backend_die, backend_margin
                write_text(logs_dir / "backend_status.txt", "PASS\n")

                collect_final_artifacts(problem, out_dir, problem_stem)
                suffix = f"_{full_iter}_{synth_iter}_{backend_iter}"
                collect_final_reports(problem, logs_dir, suffix)
                collect_final_reports(problem, logs_dir)
                closed_netlist = out_dir / f"{problem_stem}_closed.v"
                shutil.copyfile(out_dir / "closed_raw.v", closed_netlist)

                finish_report_text = read_text(logs_dir / f"finish{suffix}.rpt")
                write_finish_analysis(logs_dir, f"finish{suffix}", finish_report_text)
                timing_metrics = parse_finish_timing(finish_report_text)
                timing_summary = "\n".join(
                    [
                        f"wns={timing_metrics.get('wns')}",
                        f"tns={timing_metrics.get('tns')}",
                        f"worst_slack={timing_metrics.get('worst_slack')}",
                        f"period_min={timing_metrics.get('period_min')}",
                        f"target_period={problem.clock_period_ns}",
                        f"synth_strategy={synth_strategy.name}",
                        f"backend_iter={backend_iter}",
                        "",
                    ]
                )
                write_text(logs_dir / "timing_summary.txt", timing_summary)
                write_text(logs_dir / f"timing_summary{suffix}.txt", timing_summary)
                if is_better_timing(timing_metrics, best_metrics, problem.clock_period_ns):
                    best_metrics = dict(timing_metrics)
                    shutil.copyfile(rtl_path, best_rtl_path)
                    write_text(
                        best_timing_path,
                        "\n".join(
                            [
                                f"full_iter={full_iter}",
                                f"synth_iter={synth_iter}",
                                f"backend_iter={backend_iter}",
                                timing_summary,
                            ]
                        ),
                    )

                renamed_closed = gls_dir / f"{problem_stem}_closed_renamed.v"
                closed_filelist = gls_dir / "sky130_wrappers_closed_only.f"
                rename_netlist_top(closed_netlist, renamed_closed, problem.top_name, renamed_top)
                build_gls_filelist(renamed_closed, model_root, closed_filelist)

                closed_gls_out = gls_dir / f"{problem_stem}_closed_clean.out"
                rc, out, err = compile_gls(closed_filelist, model_root, renamed_closed, wrapper_path, tb_path, closed_gls_out)
                append_log(logs_dir, "gls_closed_compile.log", f"STDOUT:\n{out}\nSTDERR:\n{err}")
                if rc != 0:
                    backend_ok = False
                    break

                rc, out, err = run_sim(closed_gls_out)
                append_log(logs_dir, "gls_closed_run.log", f"STDOUT:\n{out}\nSTDERR:\n{err}")
                if rc != 0 or not detect_sim_pass(out, err):
                    backend_ok = False
                    break
                write_text(logs_dir / "gls_closed_status.txt", "PASS\n")

                if timing_is_closed(timing_metrics, problem.clock_period_ns):
                    backend_timing_closed = True
                    break

                last_timing_excerpt = "\n".join(
                    [
                        timing_summary,
                        "Final report excerpt:",
                        finish_report_text[:12000],
                    ]
                )
                break

            if not backend_ok:
                continue

            if not backend_timing_closed:
                continue

            summary = "\n".join(
                [
                    f"spec={spec_path}",
                    f"rtl={rtl_path}",
                    f"tb={tb_path}",
                    f"config={config_path}",
                    f"gds={out_dir / (problem_stem + '.gds')}",
                    f"synth_netlist={synth_netlist}",
                    f"closed_netlist={closed_netlist}",
                    f"wrapper={wrapper_path}",
                    f"models={model_root}",
                    f"die_area={die_size}x{die_size}",
                    f"synth_strategy={synth_strategy.name}",
                    f"wns={timing_metrics.get('wns')}",
                    f"tns={timing_metrics.get('tns')}",
                    f"period_min={timing_metrics.get('period_min')}",
                    "status=PASS",
                    "",
                ]
            )
            write_text(logs_dir / "final_status.txt", summary)
            return True

        shutil.copyfile(frozen_rtl, rtl_path)
        fix_timing_errors(str(spec_path), str(rtl_path), last_timing_excerpt or "All synthesis strategies and backend timing repair failed to close timing.")

    if best_rtl_path.exists():
        shutil.copyfile(best_rtl_path, rtl_path)
    write_text(logs_dir / "final_status.txt", "status=FAIL\n")
    return False


def main():
    parser = argparse.ArgumentParser(description="Spec-to-GDS2 automation with Codex-driven RTL iteration.")
    parser.add_argument("--spec", required=True, help="Path to YAML spec")
    parser.add_argument("--tb", required=True, help="Path to Verilog testbench")
    parser.add_argument("--rtl", required=True, help="Path to RTL file")
    parser.add_argument("--logs", required=True, help="Directory for logs")
    parser.add_argument("--openroad-root", default="openroad", help="Workspace directory for OpenROAD collateral")
    parser.add_argument(
        "--reuse-existing-rtl",
        action="store_true",
        help="Skip initial RTL generation and start from the existing RTL file",
    )
    args = parser.parse_args()

    spec_path = Path(args.spec)
    tb_path = Path(args.tb)
    rtl_path = Path(args.rtl)
    logs_dir = Path(args.logs)
    work_root = Path(args.openroad_root)

    ok = try_behavioral_loop(
        spec_path=spec_path,
        tb_path=tb_path,
        rtl_path=rtl_path,
        log_dir=logs_dir,
        reuse_existing_rtl=args.reuse_existing_rtl,
    )
    if not ok:
        print("Behavioral stage failed.")
        sys.exit(1)

    ok = run_full_flow(
        spec_path=spec_path,
        tb_path=tb_path,
        rtl_path=rtl_path,
        logs_dir=logs_dir,
        work_root=work_root,
    )
    if not ok:
        print("Backend stage failed.")
        sys.exit(1)

    print("Full flow PASS.")


if __name__ == "__main__":
    main()
