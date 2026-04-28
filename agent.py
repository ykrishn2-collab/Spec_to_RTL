import shutil
import subprocess
import sys
from pathlib import Path

MAX_ITERS = 5


def find_codex():
    codex = shutil.which("codex")
    if codex:
        return codex

    possible = [
        Path.home() / "AppData" / "Roaming" / "npm" / "codex.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "codex.CMD",
    ]
    for p in possible:
        if p.exists():
            return str(p)

    return None


def run_codex_prompt(prompt: str) -> int:
    codex_cmd = find_codex()
    if not codex_cmd:
        print("Could not find Codex CLI.")
        sys.exit(1)

    result = subprocess.run(
        [
            codex_cmd,
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            "-"
        ],
        input=prompt,
        text=True
    )
    return result.returncode


def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def summarize_spec(spec_path: str, log_dir: Path):
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


def generate_initial_rtl(spec_path: str, rtl_path: str):
    prompt = f"""
Read the hardware specification in {spec_path}.

Generate synthesizable Verilog RTL and write it to {rtl_path}.

Requirements:
- Preserve the EXACT module signature from the spec
- Do NOT add extra ports
- Use synthesizable constructs only
- Follow reset behavior exactly
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


def compile_rtl(rtl_path: str, tb_path: str, sim_out: str):
    cmd = ["iverilog", "-g2012", "-o", sim_out, rtl_path, tb_path]
    return run_cmd(cmd)


def run_sim(sim_out: str):
    cmd = ["vvp", sim_out]
    return run_cmd(cmd)


def solve_one_problem(spec_path: str, tb_path: str, rtl_path: str, logs_dir: str):
    log_dir = Path(logs_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    summarize_spec(spec_path, log_dir)
    generate_initial_rtl(spec_path, rtl_path)

    rtl_file = Path(rtl_path)
    if not rtl_file.exists():
        print(f"ERROR: RTL not created: {rtl_path}")
        return False

    sim_out = str(log_dir / "sim.out")

    for i in range(MAX_ITERS):
        print(f"\n===== ITERATION {i} =====")

        rc, out, err = compile_rtl(rtl_path, tb_path, sim_out)
        compile_log = f"STDOUT:\n{out}\nSTDERR:\n{err}"
        write_text(log_dir / f"compile_{i}.log", compile_log)

        if rc != 0:
            print("Compile failed.")
            fix_compile_errors(spec_path, rtl_path, compile_log)
            continue

        print("Compile passed.")

        rc, out, err = run_sim(sim_out)
        sim_log = f"STDOUT:\n{out}\nSTDERR:\n{err}"
        write_text(log_dir / f"sim_{i}.log", sim_log)

        # Simple heuristic: treat PASS as success
        if rc == 0 and "PASS" in out.upper():
            print("Simulation passed.")
            write_text(log_dir / "final_status.txt", "PASS\n")
            return True

        print("Simulation failed.")
        fix_simulation_errors(spec_path, rtl_path, sim_log)

    write_text(log_dir / "final_status.txt", "FAIL\n")
    return False


def main():
    problems = [
        {
            "spec": "specs/p1.yaml",
            "tb": "tb/iclad_seq_detector_tb.v",
            "rtl": "rtl/p1_design.v",
            "logs": "logs/p1"
        },
        {
            "spec": "specs/p9.yaml",
            "tb": "tb/iclad_fir_tb.v",
            "rtl": "rtl/p9_design.v",
            "logs": "logs/p9"
        }
    ]

    for p in problems:
        print(f"\n#############################")
        print(f"Running problem: {p['spec']}")
        print(f"#############################")
        ok = solve_one_problem(
            spec_path=p["spec"],
            tb_path=p["tb"],
            rtl_path=p["rtl"],
            logs_dir=p["logs"]
        )
        print(f"Result for {p['spec']}: {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()