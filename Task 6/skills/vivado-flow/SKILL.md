
---
name: vivado-flow
description: Execute goal-driven FPGA workflows in an existing AMD Vivado project using MCP tools, including device checks, constraints, synthesis, implementation, timing, resource analysis, diagnostics, and bitstream generation. Use when asked to synthesize, implement, debug a flow, analyze timing or utilization, or generate a bitstream.
---

# Vivado FPGA workflow

## Goal

Fulfill the user's requested endpoint without blindly repeating completed runs. Use MCP tool results to select the next step. Never invent Vivado results or treat absent timing constraints as timing closure.

## Available tools

- `check_device_part()` verifies/sets the configured approved target device.
- `check_constraints()` checks available physical top-level I/O assignments.
- `run_synthesis()` executes synthesis and returns diagnostic counts.
- `read_synthesis_diagnostics()` returns filtered synthesis warnings/errors.
- `run_implementation()` runs placement and routing, checking synthesis readiness first.
- `read_implementation_diagnostics()` returns filtered implementation warnings/errors.
- `analyze_timing()` returns timing metrics and constraint coverage.
- `read_timing_details(detail_type="setup"|"hold"|"checks")` returns targeted timing details.
- `analyze_resources()` returns FPGA resource utilization.
- `generate_bitstream()` generates/checks the `.bit` file after implementation prerequisites.

Only call tools that the MCP server actually exposes. Ask for a missing capability rather than pretending to have it.

## Workflow decision rules

### User requests project creation

1. Check whether the project already exists.
2. If the project does not exist, call create_project().
3. Check the execution result.
4. If creation fails, inspect the Vivado log and identify errors.
5. Report project creation status and any problems.
6. Stop. Do not perform simulation or synthesis unless requested.

### User requests behavioral simulation

1. Verify that the Vivado project exists.
2. Call run_behavioral_simulation().
3. Call read_vivado_log(step="behavioral_simulation").
4. Analyze individual test results, failures, and coverage.
5. For the current regression, verify:
   - 7 tests passed
   - 0 tests failed
   - 100% functional coverage
6. If simulation fails, analyze the RTL and failure reasons.
7. Recommend corrections, or modify authorized RTL if permitted.
8. Report simulation results and stop.

### User requests synthesis

1. Call `check_device_part()`, then `check_constraints()`; stop and report if either fails.
2. Call `run_synthesis()`.
3. If synthesis fails or reports any warnings, call `read_synthesis_diagnostics()` and analyze the *actual* messages.
4. Report status, error/critical-warning/warning counts, cause and recommended next action. Do not proceed to implementation unless requested.

### User requests implementation

1. Attempt `run_implementation()`; it checks whether synthesis is ready.
2. If it reports `SYNTHESIS_NOT_READY`, verify device and constraints, call `run_synthesis()`, inspect diagnostics as necessary, and retry implementation **once** if synthesis succeeds. Stop on any blocking prerequisite failure.
3. Read implementation diagnostics when errors or warnings are reported.
4. If implementation succeeds, call `analyze_timing()` and `analyze_resources()` when available. Inspect detailed timing only where needed.
5. Report whether routing succeeded, whether timing is met/violated/unconstrained, and resource usage. Do not generate a bitstream unless requested.

### User requests bitstream generation

1. Establish implementation readiness using the available implementation result/tools; execute missing prerequisites as above, without unlimited retries.
2. Call `analyze_timing()` before accepting the design as timing-closed. If timing is violated or unconstrained, explain the limitation. Do not claim timing closure; do not silently waive this gate. For a demonstrator with intentionally unconstrained combinational logic, require explicit user acceptance before proceeding.
3. When the required constraints and readiness conditions are satisfied, call `generate_bitstream()`.
4. Report status and the actual bitstream path returned by the tool.

### User requests diagnostics or reports only

Use the relevant `read_*_diagnostics`, `analyze_timing`, `read_timing_details`, or `analyze_resources` tool. Do not rerun synthesis or implementation merely to explain an existing result unless it is unavailable or stale.

## General rules

- Check `exit_code` AND the Tcl `RESULT ... status=SUCCESS` for execution stages. A successful tool call is not necessarily a successful Vivado run.
- Treat `timing_status=UNCONSTRAINED` differently from a timing pass; WNS/TNS marked `NA` are not zero.
- Distinguish a non-blocking warning from a functional, DRC, or timing issue. Base diagnoses on exact messages, not guessed Vivado IDs.
- Never invent FPGA pin locations, device settings, clock periods, or timing exceptions.
- Do not modify RTL/XDC or change the target board unless the user has authorized the action and the corresponding tool permits it.
- Avoid repeated successful tool calls and use at most one automatic synthesis-recovery retry during this introductory workflow.
- Prefer brief tool summaries and filtered diagnostics over full Vivado logs to reduce token consumption.
- Report what was done, what was skipped, any unresolved blocker, and recommended next action.
