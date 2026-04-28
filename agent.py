"""
Spec-to-RTL Agent
=================
Reads a YAML hardware specification, generates synthesizable Verilog
using Codex CLI, compiles with iverilog, simulates with vvp, and
iteratively repairs errors until the testbench passes.

Usage:
    python agent.py
"""

import subprocess
import sys
import shutil
import os
from pathlib import Path

MAX_ITERS  = 5
CODEX_PATH = r"C:\Users\kiran\AppData\Roaming\npm\codex.cmd"


# ── Codex caller ──────────────────────────────────────────────────────────────

def find_codex() -> str:
    """Find the Codex CLI executable. Falls back to hardcoded Windows path."""
    # 1. Try PATH first (works on macOS / Linux / Windows if PATH is set)
    found = shutil.which("codex")
    if found:
        return found
    # 2. Hardcoded Windows npm path
    if Path(CODEX_PATH).exists():
        return CODEX_PATH
    # 3. Generic Windows fallback
    candidates = [
        Path.home() / "AppData" / "Roaming" / "npm" / "codex.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "codex",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    print("ERROR: Codex CLI not found.")
    print("Install it with:  npm install -g @openai/codex")
    print("Then log in with: codex")
    sys.exit(1)


def call_codex(prompt: str) -> int:
    """Send a prompt to Codex CLI and return the exit code."""
    codex = find_codex()

    # Encode prompt as UTF-8 bytes explicitly — prevents Windows encoding errors
    prompt_bytes = prompt.encode("utf-8")

    result = subprocess.run(
        [codex,
         "exec",
         "--dangerously-bypass-approvals-and-sandbox",
         "--skip-git-repo-check",
         "-"],
        input=prompt_bytes,
        shell=True
    )
    return result.returncode


# ── EDA tool calls ────────────────────────────────────────────────────────────

def run_cmd(cmd: list):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def compile_rtl(rtl_path: str, tb_path: str, sim_out: str):
    return run_cmd(["iverilog", "-g2012", "-o", sim_out, rtl_path, tb_path])


def simulate(sim_out: str):
    return run_cmd(["vvp", sim_out])


# ── Utilities ─────────────────────────────────────────────────────────────────

def write_log(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def check_dependencies():
    """Check iverilog and codex are available before starting."""
    print("\n[Checking dependencies]")
    if shutil.which("iverilog"):
        print("  iverilog : OK")
    else:
        print("  iverilog : NOT FOUND")
        print("  Install from http://bleyer.org/icarus/ and add to PATH.")
        sys.exit(1)

    if find_codex():
        print("  codex    : OK")
    print()


# ── Agent stages ──────────────────────────────────────────────────────────────

def summarize_spec(spec_path: str):
    """Ask Codex to read and summarize the YAML spec before generating RTL."""
    prompt = f"""Read the hardware specification at {spec_path}.

Summarize the following:
1. Module name
2. Port list — name, direction, and type of each port
3. Reset behavior — synchronous or asynchronous, active high or low
4. Logic type — sequential (clocked) or combinational
5. Expected function — what the module does in plain terms

Do not write any Verilog yet. Print the summary only.
"""
    print("  --> Summarizing specification...")
    rc = call_codex(prompt)
    print(f"      Codex exit code: {rc}")


def generate_rtl(spec_path: str, rtl_path: str):
    """Ask Codex to generate initial RTL from the spec."""
    prompt = f"""Read the hardware specification at {spec_path}.

Generate a complete synthesizable Verilog module and write it to {rtl_path}.

Requirements:
- Use EXACTLY the module signature defined in the spec — same name, same ports, same directions
- Do NOT add, remove, or rename any ports
- Use synthesizable constructs only — no #delays, no $display, no non-synthesizable initial blocks
- Implement the reset behavior exactly as described in the spec
- Do not run any simulation — only write the Verilog file
"""
    print("  --> Generating initial RTL...")
    rc = call_codex(prompt)
    print(f"      Codex exit code: {rc}")


def repair_compile(spec_path: str, rtl_path: str, error_log: str):
    """Ask Codex to fix a compile error in the RTL."""
    prompt = f"""The Verilog file at {rtl_path} failed to compile with iverilog.

Fix ONLY the file at {rtl_path}.

Rules you must not break:
- Preserve the EXACT module signature from {spec_path}
- Do NOT add or remove any ports
- Do NOT modify the testbench file
- Use synthesizable constructs only

Compiler error output:
{error_log}
"""
    print("  --> Repairing compile error...")
    rc = call_codex(prompt)
    print(f"      Codex exit code: {rc}")


def repair_simulation(spec_path: str, rtl_path: str, sim_log: str):
    """Ask Codex to fix a simulation mismatch in the RTL."""
    prompt = f"""The Verilog file at {rtl_path} compiles successfully but fails simulation.

Fix ONLY the logic inside {rtl_path}.

Rules you must not break:
- Preserve the EXACT module signature from {spec_path}
- Do NOT add or remove any ports
- Do NOT modify the testbench file
- Use synthesizable constructs only

Simulation output showing expected vs observed values:
{sim_log}
"""
    print("  --> Repairing simulation mismatch...")
    rc = call_codex(prompt)
    print(f"      Codex exit code: {rc}")


# ── Main loop ─────────────────────────────────────────────────────────────────

def solve_one_problem(spec_path: str, tb_path: str,
                      rtl_path: str, logs_dir: str) -> bool:
    """
    Run the full generate → compile → simulate → repair loop
    for a single problem. Returns True if simulation passes.
    """
    log_dir = Path(logs_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    Path(rtl_path).parent.mkdir(parents=True, exist_ok=True)

    # Stage 1: summarize spec (primes Codex context)
    summarize_spec(spec_path)

    # Stage 2: generate initial RTL
    generate_rtl(spec_path, rtl_path)

    if not Path(rtl_path).exists():
        msg = f"RTL file was not created at {rtl_path}"
        print(f"  ERROR: {msg}")
        write_log(log_dir / "final_status.txt", f"FAIL - {msg}\n")
        return False

    sim_out = str(log_dir / "sim.out")

    # Stage 3: iterative compile + simulate + repair loop
    for i in range(MAX_ITERS):
        print(f"\n  [Iteration {i + 1} / {MAX_ITERS}]")

        # ── Compile ──────────────────────────────────────────
        rc, out, err = compile_rtl(rtl_path, tb_path, sim_out)
        compile_log  = f"STDOUT:\n{out}\nSTDERR:\n{err}"
        write_log(log_dir / f"compile_{i}.log", compile_log)

        if rc != 0:
            print("  Compile : FAILED")
            print(f"  {err[:400]}")
            repair_compile(spec_path, rtl_path, compile_log)
            continue

        print("  Compile : PASSED")

        # ── Simulate ─────────────────────────────────────────
        rc, out, err = simulate(sim_out)
        sim_log = f"STDOUT:\n{out}\nSTDERR:\n{err}"
        write_log(log_dir / f"sim_{i}.log", sim_log)

        if rc == 0 and "PASS" in out.upper():
            print("  Simulate: PASSED")
            write_log(log_dir / "final_status.txt", "PASS\n")
            return True

        print("  Simulate: FAILED")
        print(f"  {out[:400]}")
        repair_simulation(spec_path, rtl_path, sim_log)

    # Ran out of iterations
    write_log(log_dir / "final_status.txt", "FAIL\n")
    print(f"\n  Max iterations reached. Check logs in {logs_dir}/")
    return False


def main():
    # ── Problem definitions ───────────────────────────────────
    # To add a hidden testcase:
    #   1. Place the spec YAML in specs/
    #   2. Place the testbench in tb/
    #   3. Add an entry here and run python agent.py
    problems = [
        {
            "name": "Sequence Detector (0011)",
            "spec": "specs/p1.yaml",
            "tb":   "tb/iclad_seq_detector_tb.v",
            "rtl":  "rtl/p1_design.v",
            "logs": "logs/p1",
        },
    ]

    # ── Dependency check ──────────────────────────────────────
    check_dependencies()

    # ── Run each problem ──────────────────────────────────────
    results = {}

    for prob in problems:
        print("=" * 52)
        print(f"  Problem : {prob['name']}")
        print(f"  Spec    : {prob['spec']}")
        print("=" * 52)

        passed = solve_one_problem(
            spec_path = prob["spec"],
            tb_path   = prob["tb"],
            rtl_path  = prob["rtl"],
            logs_dir  = prob["logs"],
        )
        results[prob["name"]] = "PASS" if passed else "FAIL"

    # ── Results summary ───────────────────────────────────────
    print("\n" + "=" * 52)
    print("  RESULTS SUMMARY")
    print("=" * 52)
    all_passed = True
    for name, status in results.items():
        icon = "OK" if status == "PASS" else "!!"
        print(f"  [{icon}]  {name:35s}  {status}")
        if status != "PASS":
            all_passed = False
    print("=" * 52)
    if all_passed:
        print("  All problems passed.")
    else:
        print("  Some problems failed. Check logs/ for details.")
    print("=" * 52 + "\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()