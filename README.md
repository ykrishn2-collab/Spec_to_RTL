# Spec-to-RTL Agent
### ICLAD Hackathon 2025 — ASU Spec2Tapeout Track

An AI-driven agent that reads a YAML hardware specification,
generates synthesizable Verilog using Codex CLI, and iteratively
repairs errors using iverilog and vvp feedback.

---

## Requirements

| Tool | Purpose | Install |
|---|---|---|
| Python 3.8+ | Orchestrator | https://python.org |
| Node.js + Codex CLI | LLM executor | `npm install -g @openai/codex` |
| Icarus Verilog | Compile + simulate | http://bleyer.org/icarus/ |

---

## Setup (one time, any machine)

### 1. Install Codex CLI
npm install -g @openai/codex
### 2. Log into Codex with your OpenAI / ASU account
codex
Authenticate and then exit the interactive session.

### 3. Install Icarus Verilog
- **Windows**: http://bleyer.org/icarus/ — check "Add to PATH" during install
- **macOS**: `brew install icarus-verilog`
- **Linux**: `sudo apt install iverilog`

### 4. Install Python dependencies
pip install -r requirements.txt
---

## Run
python agent.py
The agent will:
1. Check all dependencies
2. Summarize the spec
3. Generate RTL
4. Compile and simulate
5. Repair errors automatically
6. Print a final PASS / FAIL summary

---

## Output files

| Path | Contents |
|---|---|
| `rtl/p1_design.v` | Generated Verilog |
| `logs/p1/compile_N.log` | Compile log for iteration N |
| `logs/p1/sim_N.log` | Simulation log for iteration N |
| `logs/p1/final_status.txt` | PASS or FAIL |

---

## Adding hidden test cases

1. Place the YAML spec in `specs/`
2. Place the testbench in `tb/`
3. Add an entry to the `problems` list in `agent.py`
4. Run `python agent.py`