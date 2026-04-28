"""
Spec-to-RTL Agent — Full Flow
==============================
Stage 1: Spec → RTL → Behavioral simulation (Codex + iverilog)
Stage 2: RTL → Synthesis → Place+Route → GDS (OpenROAD via Docker)

Usage:
    python agent.py                  # behavioral only
    python agent.py --full-flow      # behavioral + physical design
"""

import argparse
import re
import shutil
import subprocess
import sys
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_RTL_ITERS      = 5
MAX_SYNTH_ITERS    = 3
MAX_BACKEND_ITERS  = 3
CODEX_PATH         = r"C:\Users\kiran\AppData\Roaming\npm\codex.cmd"
DOCKER_IMAGE       = "openroad/flow-ubuntu22.04-builder"
DOCKER_ORFS        = "/OpenROAD-flow-scripts/flow"
DOCKER_OPENROAD    = "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad"
DOCKER_YOSYS       = "/usr/local/bin/yosys"


# ── Data classes ──────────────────────────────────────────────────────────────

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


# ── Codex caller ──────────────────────────────────────────────────────────────

def find_codex() -> str:
    found = shutil.which("codex")
    if found:
        return found
    if Path(CODEX_PATH).exists():
        return CODEX_PATH
    for p in [
        Path.home() / "AppData" / "Roaming" / "npm" / "codex.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "codex",
    ]:
        if p.exists():
            return str(p)
    print("ERROR: Codex CLI not found.")
    print("Install: npm install -g @openai/codex  then run: codex")
    sys.exit(1)


def call_codex(prompt: str) -> int:
    codex = find_codex()
    result = subprocess.run(
        [codex, "exec",
         "--dangerously-bypass-approvals-and-sandbox",
         "--skip-git-repo-check", "-"],
        input=prompt.encode("utf-8"),
        shell=True
    )
    return result.returncode


# ── Docker runner ─────────────────────────────────────────────────────────────

def to_docker_path(path: Path) -> str:
    """Convert a Windows absolute path to a Docker /workspace-relative path."""
    project_root = Path(__file__).parent.resolve()
    try:
        relative = path.resolve().relative_to(project_root)
        return f"/workspace/{relative.as_posix()}"
    except ValueError:
        drive = path.resolve().drive.rstrip(":").lower()
        rest  = path.resolve().as_posix().split(":", 1)[1]
        return f"/{drive}{rest}"


def run_docker(command: str) -> Tuple[int, str, str]:
    """Run a bash command inside the OpenROAD Docker container."""
    #project_root = Path(__file__).parent.resolve()
    #drive  = project_root.drive.rstrip(":").lower()
    #rest   = project_root.as_posix().split(":", 1)[1]
    #mount = project_root.as_posix()
    import os
    # os.path.abspath(__file__) always returns a full Windows path: D:\path\to\dir
    # Replacing backslashes gives D:/path/to/dir which Docker Desktop on Windows accepts.
    # Path.as_posix() and drive+rest approaches both fail in different Python/env combos.
    project_root = os.path.abspath(os.path.dirname(__file__))
    mount = project_root.replace(os.sep, "/")
    print(f"  [Docker] mount path: {mount}")

    result = subprocess.run(
        ["docker", "run", "--rm",
         "-v", f"{mount}:/workspace",
         "-w", "/workspace",
         DOCKER_IMAGE,
         "bash", "-c", command],
        capture_output=True, text=True
    )
    return result.returncode, result.stdout, result.stderr


# ── Generic command runner ────────────────────────────────────────────────────

def run_cmd(cmd: list) -> Tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


# ── File helpers ──────────────────────────────────────────────────────────────

def write_log(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── Spec parser ───────────────────────────────────────────────────────────────

def parse_spec(spec_path: Path) -> ProblemSpec:
    raw = spec_path.read_text(encoding="utf-8")
    import re as _re
    raw_clean = _re.sub(r'(?m)^  (stimulus|sample_usage):.*?(?=^  \S|\Z)', '', raw, flags=_re.DOTALL)
    if yaml:
        data = yaml.safe_load(raw_clean)
    else:
        raise RuntimeError("pyyaml not installed. Run: pip install pyyaml")

    top_name, body = next(iter(data.items()))
    module_sig     = body["module_signature"].strip()
    clock_ns       = float(str(body["clock_period"]).lower().replace("ns", ""))
    ports          = [PortSpec(p["name"], p["direction"], str(p["type"]).strip())
                      for p in body["ports"]]
    clock_port     = next(p.name for p in ports
                          if p.name.lower() in {"clk", "clock"})
    reset_ports    = [p.name for p in ports
                      if "rst" in p.name.lower() or "reset" in p.name.lower()]

    return ProblemSpec(
        top_name         = top_name,
        module_signature = module_sig,
        clock_period_ns  = clock_ns,
        ports            = ports,
        clock_port       = clock_port,
        reset_ports      = reset_ports,
    )


# ── EDA tools ─────────────────────────────────────────────────────────────────

def compile_rtl(rtl: str, tb: str, sim_out: str) -> Tuple[int, str, str]:
    return run_cmd(["iverilog", "-g2012", "-o", sim_out, rtl, tb])


def simulate(sim_out: str) -> Tuple[int, str, str]:
    return run_cmd(["vvp", sim_out])


def detect_sim_pass(stdout: str, stderr: str) -> bool:
    text = f"{stdout}\n{stderr}".upper()
    return "PASS" in text and "FAIL" not in text


def validate_rtl(problem: ProblemSpec, rtl_path: Path) -> Tuple[bool, str]:
    if not rtl_path.exists():
        return False, f"RTL file missing: {rtl_path}"
    text = read_text(rtl_path)
    if not text.strip():
        return False, "RTL file is empty"
    if not re.search(rf"\bmodule\s+{re.escape(problem.top_name)}\b", text):
        return False, f"Module {problem.top_name} not found in RTL"
    if "endmodule" not in text:
        return False, "Missing endmodule"
    return True, "OK"


# ── Codex prompts ─────────────────────────────────────────────────────────────

def summarize_spec(spec_path: str):
    print("  --> Summarizing specification...")
    call_codex(f"""Read the hardware specification at {spec_path}.
Summarize:
1. Module name
2. Port list (name, direction, type)
3. Reset behavior
4. Sequential or combinational
5. Expected function
Do not write Verilog yet.""")


def generate_rtl(spec_path: str, rtl_path: str, clock_ns: float):
    print("  --> Generating RTL...")
    call_codex(f"""Read the hardware specification at {spec_path}.
Generate a complete synthesizable Verilog module and write it to {rtl_path}.
Requirements:
- Use EXACTLY the module signature from the spec
- Do NOT add, remove, or rename any ports
- Synthesizable constructs only — no #delays, no non-synthesizable initial blocks
- Follow the reset behavior exactly
- Choose timing-friendly microarchitecture: short combinational paths,
  balanced logic trees, clean register staging where the spec allows
- Target clock period is {clock_ns} ns on Sky130 HD
- Do not run simulation""")


def repair_compile(spec_path: str, rtl_path: str, error_log: str):
    print("  --> Repairing compile error...")
    call_codex(f"""The Verilog at {rtl_path} failed to compile. Fix ONLY {rtl_path}.
Rules:
- Preserve EXACT module signature from {spec_path}
- Do NOT add or remove ports
- Do NOT modify the testbench
- Synthesizable constructs only
Compiler error:
{error_log}""")


def repair_simulation(spec_path: str, rtl_path: str, sim_log: str):
    print("  --> Repairing simulation mismatch...")
    call_codex(f"""The Verilog at {rtl_path} compiles but fails simulation.
Fix ONLY the logic in {rtl_path}.
Rules:
- Preserve EXACT module signature from {spec_path}
- Do NOT add or remove ports
- Do NOT modify the testbench
- Synthesizable constructs only
Simulation output:
{sim_log}""")


def repair_synthesis(spec_path: str, rtl_path: str, synth_log: str):
    print("  --> Repairing synthesis error (Yosys/Sky130 compatibility)...")
    call_codex(f"""The Verilog at {rtl_path} passed simulation but failed Yosys synthesis for Sky130 HD.
 
Fix ONLY {rtl_path}. Preserve the EXACT module signature from {spec_path}.
 
Common Yosys/Sky130 incompatibilities to fix — check and eliminate ALL of these:
 
1. UNPACKED ARRAYS in always @* combinational blocks
   BAD:  logic [W-1:0] arr [0:N-1];  always @* begin arr[i] = ...; end
   GOOD: Flatten to a packed vector: logic [N*W-1:0] arr_flat;
         Or use a for-generate to create named signals: wire [W-1:0] term0, term1, ...;
 
2. AUTOMATIC FUNCTIONS with local variables
   BAD:  function automatic logic [W-1:0] foo(...); logic [W-1:0] tmp; ...
   GOOD: function logic [W-1:0] foo(...); reg [W-1:0] tmp; ... (remove automatic)
 
3. UNPACKED ARRAY PORTS (packed multidimensional is OK, unpacked port is not)
   BAD:  input logic [W-1:0] arr [0:N-1]
   GOOD: input logic [N-1:0][W-1:0] arr  (packed — this is fine for Sky130)
 
4. $clog2() IN PORT WIDTHS — move to localparam
   BAD:  output logic [2*W+$clog2(N):0] y
   GOOD: localparam ACC_W = 2*W+$clog2(N)+1;  output logic [ACC_W-1:0] y
         (but keep port signature matching spec exactly)
 
5. ALWAYS_FF / ALWAYS_COMB — replace with always @(posedge clk) / always @*
   Some Yosys versions reject always_ff/always_comb keywords
 
The preferred architecture for a FIR filter on Sky130 is the TRANSPOSED FORM:
- One tap_accum register array [0:N-2] (registered, not combinational)
- One multiply-accumulate per tap in a single always @(posedge clk) block
- No combinational unpacked arrays at all
 
Synthesis log excerpt:
{synth_log[:6000]}""")
 
def scan_and_repair_rtl_for_synthesis(spec_path: str, rtl_path: str):
    """Check RTL for known Yosys incompatibilities and ask Codex to fix them proactively."""
    rtl_text = Path(rtl_path).read_text(encoding="utf-8") if Path(rtl_path).exists() else ""
    import re
    issues = []
 
    # Check for unpacked arrays in combinational always blocks
    has_unpacked_in_always = bool(re.search(
        r'always\s*@\s*\*.*?(?:logic|reg)\s+\[.*?\]\s+\w+\s*\[', rtl_text, re.DOTALL
    ))
    # Simpler: any unpacked array declaration + always @*
    has_unpacked_decl = bool(re.search(r'(?:logic|reg)\s+(?:signed\s+|unsigned\s+)?\[.*?\]\s+\w+\s*\[.*?\]\s*;', rtl_text))
    has_always_star   = bool(re.search(r'always\s*@\s*\*', rtl_text))
    if has_unpacked_decl and has_always_star:
        issues.append("unpacked array declaration with always @* block (Yosys cannot synthesize unpacked arrays in combinational logic)")
 
    # Check for automatic functions with LOCAL variable declarations (not just the keyword)
    # Yosys 0.63+ supports function automatic, but local array variables inside can fail
    if re.search(r'function\s+automatic', rtl_text):
        fn_body = re.search(r'function\s+automatic.*?endfunction', rtl_text, re.DOTALL)
        if fn_body and re.search(r'(?:logic|reg)\s+\[.*?\]\s+\w+\s*\[', fn_body.group()):
            issues.append("unpacked array inside 'function automatic' body")
 
    if not issues:
        return  # RTL looks clean, skip
 
    issue_list = "\n".join(f"  - {iss}" for iss in issues)
    print(f"  --> Pre-synthesis scan found {len(issues)} Yosys compatibility issue(s) — asking Codex to fix...")
    call_codex(f"""The Verilog at {rtl_path} has constructs that Yosys/Sky130 cannot synthesize.
 
Detected issues:
{issue_list}
 
Fix ONLY {rtl_path}. Rules:
- Preserve the EXACT module signature from {spec_path}
- Do NOT add or remove ports
- Do NOT modify any testbench
- Use synthesizable constructs compatible with Yosys 0.6+ and Sky130 HD
- Replace unpacked arrays in always @* with packed vectors or a generate block
- Remove 'automatic' from functions
- Replace always_ff with always @(posedge clk), always_comb with always @*
- After fixing, verify the logic is functionally equivalent to before
 
For FIR filters specifically: use the transposed form with a registered tap_accum [0:N-2]
array and a single always @(posedge clk) block. No combinational arrays needed.""") 


def repair_timing(spec_path: str, rtl_path: str, timing_log: str):
    print("  --> Repairing timing violation...")
    call_codex(f"""The Verilog at {rtl_path} passes simulation but misses timing in OpenROAD.
Fix ONLY {rtl_path} to improve timing.
Preferred fixes in order:
1. Reduce combinational depth
2. Balance logic trees
3. Add pipeline staging where spec allows
4. Reduce fanout
Rules:
- Preserve EXACT module signature from {spec_path}
- Do NOT add or remove ports
- Synthesizable constructs only
Timing report:
{timing_log}""")


# ── Behavioral loop ───────────────────────────────────────────────────────────

def behavioral_loop(spec_path: str, tb_path: str,
                    rtl_path: str, logs_dir: str,
                    reuse_rtl: bool = False) -> bool:
    log_dir = Path(logs_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    Path(rtl_path).parent.mkdir(parents=True, exist_ok=True)

    problem = parse_spec(Path(spec_path))
    summarize_spec(spec_path)

    if not reuse_rtl:
        generate_rtl(spec_path, rtl_path, problem.clock_period_ns)
        valid, issue = validate_rtl(problem, Path(rtl_path))
        if not valid:
            print(f"  ERROR: {issue}")
            write_log(log_dir / "behavioral_status.txt", f"FAIL - {issue}\n")
            return False

    sim_out = str(log_dir / "sim.out")

    for i in range(MAX_RTL_ITERS):
        print(f"\n  [RTL Iteration {i+1}/{MAX_RTL_ITERS}]")

        rc, out, err = compile_rtl(rtl_path, tb_path, sim_out)
        compile_log  = f"STDOUT:\n{out}\nSTDERR:\n{err}"
        write_log(log_dir / f"compile_{i}.log", compile_log)

        if rc != 0:
            print("  Compile : FAILED")
            print(f"  {err[:300]}")
            repair_compile(spec_path, rtl_path, compile_log)
            continue

        print("  Compile : PASSED")

        rc, out, err = simulate(sim_out)
        sim_log = f"STDOUT:\n{out}\nSTDERR:\n{err}"
        write_log(log_dir / f"sim_{i}.log", sim_log)

        if rc == 0 and detect_sim_pass(out, err):
            print("  Simulate: PASSED")
            write_log(log_dir / "behavioral_status.txt", "PASS\n")
            return True

        print("  Simulate: FAILED")
        print(f"  {out[:300]}")
        repair_simulation(spec_path, rtl_path, sim_log)

    write_log(log_dir / "behavioral_status.txt", "FAIL\n")
    return False


# ── Physical design (Docker) ──────────────────────────────────────────────────

def write_sdc(problem: ProblemSpec, sdc_path: Path):
    lines = [
        f"create_clock -name {problem.clock_port} "
        f"-period {problem.clock_period_ns} "
        f"[get_ports {problem.clock_port}]"
    ]
    for p in problem.ports:
        if p.direction == "input" and p.name != problem.clock_port:
            lines.append(
                f"set_input_delay 0.5 -clock {problem.clock_port} "
                f"[get_ports {p.name}]"
            )
    for p in problem.ports:
        if p.direction == "output":
            lines.append(
                f"set_output_delay 0.5 -clock {problem.clock_port} "
                f"[get_ports {p.name}]"
            )
    sdc_path.parent.mkdir(parents=True, exist_ok=True)
    sdc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  SDC written: {sdc_path}")


def write_config(problem: ProblemSpec, rtl_path: Path, sdc_path: Path,
                 config_path: Path, die: int = 240, margin: int = 30,
                 density: float = 0.35, extra_env: dict = None):
    core_ll = margin
    core_ur = die - margin
    lines = [
        f"export DESIGN_NAME      = {problem.top_name}",
        "export PLATFORM         = sky130hd",
        f"export VERILOG_FILES    = {to_docker_path(rtl_path)}",
        f"export SDC_FILE         = {to_docker_path(sdc_path)}",
        f"export DIE_AREA         = 0 0 {die} {die}",
        f"export CORE_AREA        = {core_ll} {core_ll} {core_ur} {core_ur}",
        f"export PLACE_DENSITY    = {density:.2f}",
        "export TNS_END_PERCENT  = 100",
        "export LEC_CHECK        = 0",
    ]
    if extra_env:
        lines += [f"export {k} = {v}" for k, v in extra_env.items()]
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  config.mk written: {config_path}")


def run_synthesis(config_path: Path, log_path: Path) -> Tuple[bool, str]:
    cfg = to_docker_path(config_path)
    cmd = (
        f"cd {DOCKER_ORFS} && "
        f"make DESIGN_CONFIG={cfg} "
        f"OPENROAD_EXE={DOCKER_OPENROAD} "
        f"YOSYS_EXE={DOCKER_YOSYS} "
        f"clean_all synth"
    )
    rc, out, err = run_docker(cmd)
    text = f"STDOUT:\n{out}\nSTDERR:\n{err}"
    write_log(log_path, text)
    return rc == 0, text


def run_backend(config_path: Path, log_path: Path) -> Tuple[bool, str]:
    cfg = to_docker_path(config_path)
    cmd = (
        f"cd {DOCKER_ORFS} && "
        f"make DESIGN_CONFIG={cfg} "
        f"OPENROAD_EXE={DOCKER_OPENROAD} "
        f"YOSYS_EXE={DOCKER_YOSYS} "
        f"clean_place && "
        f"make DESIGN_CONFIG={cfg} "
        f"OPENROAD_EXE={DOCKER_OPENROAD} "
        f"YOSYS_EXE={DOCKER_YOSYS}"
    )
    rc, out, err = run_docker(cmd)
    text = f"STDOUT:\n{out}\nSTDERR:\n{err}"
    write_log(log_path, text)
    return rc == 0, text


def parse_timing(log_text: str) -> Dict[str, Optional[float]]:
    def get(pattern):
        m = re.search(pattern, log_text, re.IGNORECASE)
        return float(m.group(1)) if m else None

    return {
        "wns":  get(r"wns\s+max\s+(-?[\d.]+)"),
        "tns":  get(r"tns\s+max\s+(-?[\d.]+)"),
        "area": get(r"design area\s+([\d.]+)"),
    }


def timing_closed(metrics: dict, target_ns: float) -> bool:
    wns = metrics.get("wns")
    return wns is not None and wns >= 0.0


def get_synth_strategies(problem: ProblemSpec) -> List[SynthStrategy]:
    top = problem.top_name
    return [
        SynthStrategy("baseline",      {}),
        SynthStrategy("retime",        {"SYNTH_RETIME_MODULES": top}),
        SynthStrategy("hier_opt",      {"SYNTH_OPT_HIER": "1"}),
    ]


def full_flow(spec_path: str, rtl_path: str,
              logs_dir: str, work_dir: str) -> bool:
    """Run physical design via Docker OpenROAD."""
    problem  = parse_spec(Path(spec_path))
    log_dir  = Path(logs_dir)
    work     = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)

    sdc_path    = work / "constraint.sdc"
    config_path = work / "config.mk"

    write_sdc(problem, sdc_path)

    strategies = get_synth_strategies(problem)
    best_metrics = {}
    best_rtl_path = work / "best_rtl.v"

    for full_iter in range(MAX_RTL_ITERS):
        print(f"\n  [Full-flow RTL iteration {full_iter}]")

        for si, strategy in enumerate(strategies):
            print(f"  Synth strategy: {strategy.name}")
            write_config(
                problem, Path(rtl_path), sdc_path, config_path,
                extra_env=strategy.env
            )

            synth_ok, synth_log = run_synthesis(
                config_path, log_dir / f"synth_{full_iter}_{si}.log"
            )
            write_log(
                log_dir / f"synth_{full_iter}_{si}_strategy.txt",
                f"strategy={strategy.name}\n"
            )

            if not synth_ok:
                print("  Synthesis: FAILED")
                if full_iter < MAX_RTL_ITERS - 1:
                    repair_synthesis(spec_path, rtl_path, synth_log[:8000])
                continue

            print("  Synthesis: PASSED")

            for bi in range(MAX_BACKEND_ITERS):
                print(f"  Backend attempt {bi+1}/{MAX_BACKEND_ITERS}")
                backend_ok, backend_log = run_backend(
                    config_path,
                    log_dir / f"backend_{full_iter}_{si}_{bi}.log"
                )

                if not backend_ok:
                    print("  Backend: FAILED — adjusting floorplan")
                    # Increase die size on failure
                    die = 240 + (bi + 1) * 48
                    write_config(
                        problem, Path(rtl_path), sdc_path, config_path,
                        die=die, density=0.35 - bi * 0.05,
                        extra_env=strategy.env
                    )
                    continue

                print("  Backend: PASSED")
                metrics = parse_timing(backend_log)
                write_log(
                    log_dir / f"timing_{full_iter}_{si}_{bi}.txt",
                    f"wns={metrics.get('wns')}\n"
                    f"tns={metrics.get('tns')}\n"
                    f"area={metrics.get('area')}\n"
                )

                if not best_metrics or (
                    metrics.get("wns") is not None and
                    (not best_metrics.get("wns") or
                     metrics["wns"] > best_metrics.get("wns", -999))
                ):
                    best_metrics = dict(metrics)
                    shutil.copy(rtl_path, best_rtl_path)

                if timing_closed(metrics, problem.clock_period_ns):
                    print(f"  Timing CLOSED — WNS={metrics.get('wns')} ns")
                    write_log(
                        log_dir / "final_status.txt",
                        f"PASS\nWNS={metrics.get('wns')}\n"
                        f"TNS={metrics.get('tns')}\n"
                        f"area={metrics.get('area')}\n"
                    )
                    return True

                # Timing not closed — repair and retry
                print(
                    f"  Timing not closed — "
                    f"WNS={metrics.get('wns')} ns"
                )
                if full_iter < MAX_RTL_ITERS - 1:
                    repair_timing(spec_path, rtl_path, backend_log[:8000])
                break

    if best_rtl_path.exists():
        shutil.copy(best_rtl_path, rtl_path)

    write_log(log_dir / "final_status.txt", "FAIL - timing not closed\n")
    print("  Full flow finished without timing closure.")
    print(
        f"  Best result: WNS={best_metrics.get('wns')} "
        f"TNS={best_metrics.get('tns')}"
    )
    return False


# ── Solutions collector ───────────────────────────────────────────────────────

def collect_solutions(prob_name: str, rtl_path: str,
                      logs_dir: str, work_dir: str = None):
    sol_dir = Path("solutions") / prob_name
    sol_dir.mkdir(parents=True, exist_ok=True)

    if Path(rtl_path).exists():
        shutil.copy(rtl_path, sol_dir / Path(rtl_path).name)

    if work_dir:
        for f in ["constraint.sdc", "config.mk"]:
            src = Path(work_dir) / f
            if src.exists():
                shutil.copy(src, sol_dir / f)

    status_file = Path(logs_dir) / "final_status.txt"
    status = status_file.read_text().strip() if status_file.exists() else "UNKNOWN"

    (sol_dir / "README.md").write_text(
        f"# {prob_name}\n\n"
        f"## Status\n{status}\n\n"
        f"## Files\n"
        f"- `{Path(rtl_path).name}` — generated synthesizable Verilog\n"
        f"- `constraint.sdc` — timing constraints (if full flow ran)\n"
        f"- `config.mk` — OpenROAD configuration (if full flow ran)\n",
        encoding="utf-8"
    )
    print(f"  Solutions written to {sol_dir}/")


# ── Dependency check ──────────────────────────────────────────────────────────

def check_dependencies(full_flow_mode: bool):
    print("\n[Checking dependencies]")
    ok = True

    if shutil.which("iverilog"):
        print("  iverilog : OK")
    else:
        print("  iverilog : NOT FOUND — http://bleyer.org/icarus/")
        ok = False

    if find_codex():
        print("  codex    : OK")

    if full_flow_mode:
        if shutil.which("docker"):
            print("  docker   : OK")
            # Quick test that OpenROAD image is available
            rc, out, _ = run_cmd(
                ["docker", "image", "inspect",
                 DOCKER_IMAGE, "--format", "{{.Id}}"]
            )
            if rc == 0:
                print(f"  {DOCKER_IMAGE} : OK")
            else:
                print(f"  {DOCKER_IMAGE} : NOT FOUND")
                print(f"  Run: docker pull {DOCKER_IMAGE}")
                ok = False
        else:
            print("  docker   : NOT FOUND — install Docker Desktop")
            ok = False

    if not ok:
        sys.exit(1)
    print()


# ── Problem definitions ───────────────────────────────────────────────────────

PROBLEMS = [
    {
        "name":    "p1",
        "display": "Sequence Detector (0011)",
        "spec":    "specs/p1.yaml",
        "tb":      "tb/iclad_seq_detector_tb.v",
        "rtl":     "rtl/p1_design.v",
        "logs":    "logs/p1",
        "work":    "openroad/p1",
    },
    # Uncomment to add more problems:
     {
         "name":    "p9",
         "display": "FIR Filter",
         "spec":    "specs/p9.yaml",
         "rtl":     "rtl/p9_design.v",
         "logs":    "logs/p9",
         "tb":      "tb/iclad_fir_tb.v",
         "work":    "openroad/p9",
     },
]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Spec-to-RTL Agent — ICLAD Hackathon 2025"
    )
    parser.add_argument(
        "--full-flow", action="store_true",
        help="Run physical design via OpenROAD (Docker) after sim passes"
    )
    parser.add_argument(
        "--reuse-rtl", action="store_true",
        help="Skip RTL generation and use existing RTL files"
    )
    args = parser.parse_args()

    check_dependencies(args.full_flow)

    print("=" * 55)
    print("  Spec-to-RTL Agent")
    print("  ICLAD Hackathon 2025 — ASU Spec2Tapeout Track")
    if args.full_flow:
        print("  Mode: Full flow (Behavioral + Physical Design)")
    else:
        print("  Mode: Behavioral only (Spec → RTL → Sim)")
    print("=" * 55)

    results = {}

    for prob in PROBLEMS:
        print(f"\n{'='*55}")
        print(f"  Problem : {prob['display']}")
        print(f"  Spec    : {prob['spec']}")
        print(f"{'='*55}")

        # Stage 1 — Behavioral
        behav_passed = behavioral_loop(
            spec_path = prob["spec"],
            tb_path   = prob["tb"],
            rtl_path  = prob["rtl"],
            logs_dir  = prob["logs"],
            reuse_rtl = args.reuse_rtl,
        )

        pd_passed = False

        # Stage 2 — Physical design (only if behavioral passed)
        if behav_passed and args.full_flow:
            print(f"\n  --> Starting physical design flow...")
            pd_passed = full_flow(
                spec_path = prob["spec"],
                rtl_path  = prob["rtl"],
                logs_dir  = prob["logs"],
                work_dir  = prob["work"],
            )

        # Collect outputs into solutions/
        collect_solutions(
            prob_name = prob["name"],
            rtl_path  = prob["rtl"],
            logs_dir  = prob["logs"],
            work_dir  = prob["work"] if args.full_flow else None,
        )

        if args.full_flow:
            status = "PASS" if (behav_passed and pd_passed) else (
                "BEHAV_PASS" if behav_passed else "FAIL"
            )
        else:
            status = "PASS" if behav_passed else "FAIL"

        results[prob["display"]] = status

    # Summary
    print(f"\n{'='*55}")
    print("  RESULTS SUMMARY")
    print(f"{'='*55}")
    all_passed = True
    for name, status in results.items():
        icon = "OK" if "PASS" in status else "!!"
        print(f"  [{icon}]  {name:38s}  {status}")
        if "FAIL" in status:
            all_passed = False
    print(f"{'='*55}\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()