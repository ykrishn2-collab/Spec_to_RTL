\# Spec2RTL Agent (Mini Project Phase 2)



\## Overview

This project implements an AI-based agent for Spec-to-RTL automation.



The system:

\- reads YAML hardware specs

\- generates RTL using Codex

\- compiles with iVerilog

\- simulates using testbenches

\- iteratively fixes RTL using feedback

Workflow Description

The workflow is controller-based:

\- Python sends a focused prompt to Codex to summarize the spec

\- Python sends a focused prompt to generate initial RTL

\- If compile fails, Python sends the compile log to Codex for repair

\- If compile passes, Codex runs simulation

\- If simulation fails, Python sends the simulation log to Codex for logic repair

\- The loop continues until success or iteration limit

Hidden Testcases

To run hidden testcases:

\- Place hidden spec files in specs/

\- Place matching hidden testbenches in tb/

\- Update the problems list in agent.py

\## Run



```powershell

python agent.py

