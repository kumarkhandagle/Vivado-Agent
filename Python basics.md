Python’s subprocess module lets a Python program run external programs or commands and collect their results.
For example, Python can launch Vivado, a simulator, or a Tcl script, wait for it to finish, and check whether it succeeded.

import subprocess

result = subprocess.run(
    ["python", "--version"],
    capture_output=True,
    text=True
)

print("Output:", result.stdout)
print("Errors:", result.stderr)
print("Exit code:", result.returncode)

| Item | Purpose |
|---|---|
| `["python", "--version"]` | Program and arguments to execute |
| `capture_output=True` | Capture standard output and error output |
| `text=True` | Return captured output as strings |
| `result.stdout` | Standard output from the command |
| `result.stderr` | Error or diagnostic output from the command |
| `result.returncode` | Exit code; usually `0` means success |


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


    subprocess.run() waits for the command to finish. Here, timeout=600 raises a TimeoutExpired exception if it takes longer than 600 seconds.

    With capture_output=True and text=True, all the text Vivado prints to standard output during that execution is collected in result.stdout, including its startup banner, progress messages, and reports.

    AMD documents that Vivado’s Log window displays standard output for synthesis, implementation, and simulation, and that this output is also included in vivado.log

    In your Tcl script:
exit 0

Vivado exits with success:
result.returncode == 0


If the script uses:
exit 1

Vivado exits with failure:
result.returncode == 1


For example, you can handle a synthesis error explicitly:
if {[catch {
    synth_design -top top -part xc7z010clg400-1
} error_message]} {
    puts stderr "Synthesis failed: $error_message"
    exit 1
}

puts "Synthesis completed successfully"
exit 0


timeout is the maximum time you allow the command to finish—not the actual time the Tcl script will take.
subprocess.run(    "vivado -mode batch -source run_synth.tcl",    shell=True,    timeout=300,)


Here, Python allows 300 seconds for the whole command: Vivado startup, Tcl script execution, and Vivado exit.
- If it finishes in 120 seconds, Python continues immediately.
- If it has not finished within 300 seconds, Python raises a timeout error.
The Tcl script’s actual runtime depends on its operations and the design. You choose the timeout as an upper waiting limit.
