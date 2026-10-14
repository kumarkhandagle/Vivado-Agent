# Running External Tools with Python's `subprocess` and `pathlib`

Python’s `subprocess` module lets a Python program run external programs or commands and collect their results.

For example, Python can launch Vivado, a simulator, or a Tcl script, wait for it to finish, and check whether it succeeded.

---

## System Architecture and Execution Flow

### System Components

| Component | Role |
| :--- | :--- |
| **Python controller** | Coordinates execution and collects results |
| **Tcl script** | Defines the operations Vivado performs |
| **Vivado** | Performs synthesis, implementation, and other FPGA operations |
| **AI agent** *(added later)* | Uses feedback to decide the next action |

### Execution Workflow

1. **Verify environment:** Checks that the Tcl script exists.
2. **Launch process:** Launches Vivado via `subprocess`.
3. **Verify input files:** Tcl script checks if necessary files exist.
4. **Wait:** Waits for execution to finish (respecting timeouts).
5. **Inspect status:** Checks the exit code.
6. **Parse output:** Reads generated reports and log files.
7. **Report:** Returns results or reports a failure.

---

## File and Path Management with `pathlib`

`pathlib` is a built-in Python module for working with file and folder paths in an object-oriented, cross-platform manner.

### Basic Setup and Representation

Import the `Path` class and represent a file's location:

```python
from pathlib import Path

tcl_file = Path("C:/Agents/Day1/run_synth.tcl")
```

> **Note:** `tcl_file` holds a path reference to the file, not its actual contents.

### Common `Path` Operations

| Operation | Python Code |
| :--- | :--- |
| **Check whether the file exists** | `tcl_file.is_file()` |
| **Get its filename** | `tcl_file.name` |
| **Get its containing folder** | `tcl_file.parent` |
| **Read its text content** | `tcl_file.read_text(encoding="utf-8")` |

### Checking File Existence

```python
if tcl_file.is_file():
    print("Tcl script found.")
else:
    print(f"Missing Tcl script: {tcl_file}")
```

### Joining Paths

You can join folder and file names using the `/` operator:

```python
project_dir = Path("C:/Agents/Day1")
tcl_file = project_dir / "scripts" / "run_synth.tcl"
```

Here, `/` cleanly resolves and joins path components to produce:
```text
C:\Agents\Day1\scripts\run_synth.tcl
```

---

## Basic `subprocess` Example

```python
import subprocess

result = subprocess.run(
    ["python", "--version"],
    capture_output=True,
    text=True
)

print("Output:", result.stdout)
print("Errors:", result.stderr)
print("Exit code:", result.returncode)
```

### Parameter & Attribute Reference

| Item | Purpose |
| :--- | :--- |
| `["python", "--version"]` | Program and arguments to execute |
| `capture_output=True` | Capture standard output and error output |
| `text=True` | Return captured output as strings |
| `result.stdout` | Standard output from the command |
| `result.stderr` | Error or diagnostic output from the command |
| `result.returncode` | Exit code; usually `0` means success |

---

## Running Vivado in Batch Mode

```python
import subprocess

result = subprocess.run(
    ["vivado", "-mode", "batch", "-source", "synth.tcl"],
    capture_output=True,
    text=True,
    timeout=600
)

if result.returncode == 0:
    print("Vivado command completed successfully")
else:
    print("Vivado command failed")
    print(result.stderr)
```

### Key Behaviors

* **Waiting and Timeouts:** `subprocess.run()` waits for the command to finish. Here, `timeout=600` raises a `TimeoutExpired` exception if it takes longer than 600 seconds.
* **Capturing Logs:** With `capture_output=True` and `text=True`, all the text Vivado prints to standard output during that execution is collected in `result.stdout`, including its startup banner, progress messages, and reports.
* **AMD Documentation Note:** AMD documents that Vivado’s Log window displays standard output for synthesis, implementation, and simulation, and that this output is also included in `vivado.log`.

---

## Handling Exit Codes in Tcl Scripts

In your Tcl script:

```tcl
exit 0
```

Vivado exits with success:
```python
result.returncode == 0
```

If the script uses:

```tcl
exit 1
```

Vivado exits with failure:
```python
result.returncode == 1
```

### Example: Explicit Error Handling in Tcl

```tcl
if {[catch {
    synth_design -top top -part xc7z010clg400-1
} error_message]} {
    puts stderr "Synthesis failed: $error_message"
    exit 1
}

puts "Synthesis completed successfully"
exit 0
```

---

## Understanding Command Timeouts

`timeout` is the maximum time you allow the command to finish—not the actual time the Tcl script will take.

```python
subprocess.run(
    "vivado -mode batch -source run_synth.tcl",
    shell=True,
    timeout=300,
)
```

Here, Python allows 300 seconds for the whole command: Vivado startup, Tcl script execution, and Vivado exit.

* **Finishes early:** If it finishes in 120 seconds, Python continues immediately.
* **Exceeds limit:** If it has not finished within 300 seconds, Python raises a timeout error.

> **Note:** The Tcl script’s actual runtime depends on its operations and the design complexity. Choose the timeout value as an upper safety limit.
