import pathlib
import subprocess
import datetime
import re
import shutil

from config import PROJECT_DIR, PROJECT_NAME

PROJECT_ROOT = pathlib.Path(PROJECT_DIR)
SCRIPT_DIR = PROJECT_ROOT / "scripts"
LOG_DIR = PROJECT_ROOT / "logs"


# 1. Run the project-creation Tcl script.
def create_project():
    script_file = SCRIPT_DIR / "build_project.tcl"

    log_file = LOG_DIR / "build_project.log"

    if not script_file.is_file():
        raise FileNotFoundError(f"Missing Tcl script: {script_file}")

    log_file.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "vivado",
            "-mode", "batch",
            "-source", str(script_file),
            "-log", str(log_file),
            "-tclargs", str(PROJECT_ROOT), PROJECT_NAME,
        ],
        capture_output=True,
        text=True,
        errors="replace",
        shell=True,
    )

    return {
        "exit_code": result.returncode,
        "log_file": str(log_file),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


# 2. Extract and summarize messages from a Vivado log.
def summarize_build_log(log_file, filter="default", max_messages=None):
    severity_order = ["ERROR", "CRITICAL WARNING", "WARNING", "INFO"]

    filters = {
        "errors": ["ERROR"],
        "critical": ["CRITICAL WARNING"],
        "warnings": ["WARNING"],
        "info": ["INFO"],
        "all": severity_order,
        "default": ["ERROR", "CRITICAL WARNING", "WARNING"],
    }

    if not isinstance(filter, str) or filter not in filters:
        raise ValueError("Unsupported filter.")

    if max_messages is not None:
        if type(max_messages) is not int or max_messages < 0:
            raise ValueError(
                "max_messages must be a nonnegative integer or None."
            )

    selected = filters[filter]
    log_file = pathlib.Path(log_file)

    totals = {}
    grouped_messages = {}
    retained_counts = {}

    for severity in selected:
        totals[severity] = 0
        grouped_messages[severity] = {}
        retained_counts[severity] = 0

    examples = []
    omitted_examples = 0

    # Summaries use message text rather than message IDs.
    def summarize_message(text):
        single_line = " ".join(text.split())
        lower_text = single_line.lower()

        if (
            "cannot add board part" in lower_text
            and "either invalid or not available" in lower_text
        ):
            return (
                "Board definition cannot be added because its "
                "device part is invalid or unavailable."
            )

        if "boardpart property will be unset" in lower_text:
            return "Selected board part not found; BoardPart will be unset."

        if (
            "already exists in the project" in lower_text
            and "skipping this file" in lower_text
        ):
            return "File already exists; duplicate addition skipped."

        if lower_text.startswith("exiting vivado"):
            return "Vivado is exiting."

        # Preserve the actual text for unrecognized message patterns.
        return single_line

    with log_file.open(encoding="utf-8", errors="replace") as log:
        for line_number, line in enumerate(log, start=1):
            line = line.strip()

            severity = None
            text = ""

            for candidate in selected:
                prefix = candidate + ":"

                if line.startswith(prefix):
                    severity = candidate
                    text = line[len(prefix):].strip()
                    break

            if severity is None:
                continue

            message_id = "UNTAGGED"

            if text.startswith("["):
                closing_bracket = text.find("]")

                if closing_bracket > 1:
                    candidate_id = text[1:closing_bracket].strip()

                    if candidate_id:
                        message_id = candidate_id
                        text = text[closing_bracket + 1:].strip()

            totals[severity] += 1
            severity_groups = grouped_messages[severity]

            # Keep a full example for every severity-ID group.
            if message_id not in severity_groups:
                severity_groups[message_id] = {
                    "severity": severity,
                    "id": message_id,
                    "count": 0,
                    "summary": summarize_message(text),
                    "example": text,
                    "line_number": line_number,
                }

            severity_groups[message_id]["count"] += 1

            # Limit additional examples, but count every occurrence.
            if (
                max_messages is None
                or retained_counts[severity] < max_messages
            ):
                examples.append({
                    "severity": severity,
                    "id": message_id,
                    "text": text,
                    "line_number": line_number,
                })

                retained_counts[severity] += 1
            else:
                omitted_examples += 1

    groups = []

    for severity in selected:
        for message_id in sorted(grouped_messages[severity]):
            groups.append(grouped_messages[severity][message_id])

    return {
        "totals": totals,
        "groups": groups,
        "examples": examples,
        "omitted_examples": omitted_examples,
    }


# 3. Read the project-creation Tcl script.
def read_project_script():
    script_file = SCRIPT_DIR / "build_project.tcl"

    if not script_file.is_file():
        raise FileNotFoundError(f"Missing Tcl script: {script_file}")

    content = script_file.read_text(encoding="utf-8")

    return {
        "script_file": str(script_file),
        "content": content,
        "line_count": len(content.splitlines()),
    }


# 4. Back up and edit the project-creation Tcl script.
def edit_project_script(old_text, new_text):
    script_file = SCRIPT_DIR / "build_project.tcl"

    if not isinstance(old_text, str) or not old_text.strip():
        raise ValueError("old_text must be a nonempty string.")

    if not isinstance(new_text, str):
        raise ValueError("new_text must be a string.")

    if not script_file.is_file():
        raise FileNotFoundError(f"Missing Tcl script: {script_file}")

    original_bytes = script_file.read_bytes()
    content = original_bytes.decode("utf-8")

    # Match the script's line-ending style.
    newline = "\r\n" if "\r\n" in content else "\n"

    old_text = old_text.replace("\r\n", "\n").replace("\n", newline)
    new_text = new_text.replace("\r\n", "\n").replace("\n", newline)

    if old_text == new_text:
        raise ValueError("The replacement would not change the script.")

    matches = content.count(old_text)

    if matches == 0:
        raise ValueError("old_text was not found in the script.")

    if matches > 1:
        raise ValueError(
            "old_text matches multiple locations. "
            "Include more surrounding text to identify one location."
        )

    updated_content = content.replace(old_text, new_text, 1)

    # Save the exact original file before editing.
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_file = script_file.with_name(
        f"{script_file.name}.{timestamp}.bak"
    )

    backup_file.write_bytes(original_bytes)
    script_file.write_bytes(updated_content.encode("utf-8"))

    return {
        "changed": True,
        "script_file": str(script_file),
        "backup_file": str(backup_file),
        "old_text": old_text,
        "new_text": new_text,
    }


def generate_verilog(requirement, file_path):
    from google import genai

    client = genai.Client()

    response = client.interactions.create(
        model="gemini-3.8-flash",
        system_instruction=(
            "Generate synthesizable Verilog-2001 code. "
            "Return only Verilog source code without Markdown."
        ),
        input=requirement,
        generation_config={"thinking_level": "high"}
    )

    code = response.output_text

    if not code or not code.strip():
        raise ValueError("Gemini returned empty Verilog code.")

    path = pathlib.Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as file:
        file.write(code)

    return str(path)



def rtl_update(old_text: str, new_text: str) -> str:
    """Update RTL source file."""

    # RTL file to modify.
    rtl_file = PROJECT_ROOT / "rtl" / "axil_mem.v"

    if not rtl_file.is_file():
        raise FileNotFoundError("RTL file not found.")

    # Read the existing RTL code.
    code = rtl_file.read_text(encoding="utf-8")

    if not old_text:
        raise ValueError("Old text cannot be empty.")

    if code.count(old_text) != 1:
        raise ValueError("Old text must appear exactly once.")

    # Replace the old code.
    code = code.replace(old_text, new_text, 1)

    # Save the updated RTL code.
    rtl_file.write_text(code, encoding="utf-8")

    return "SUCCESS"


def refresh_filesets():

    script_file = SCRIPT_DIR / "refresh_fileset.tcl"

    log_file = LOG_DIR / "refresh_fileset.log"

    if not script_file.is_file():
        raise FileNotFoundError(
            f"Missing Tcl script: {script_file}"
        )

    log_file.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "vivado",
            "-mode", "batch",
            "-source", str(script_file),
            "-log", str(log_file),
            "-tclargs", str(PROJECT_ROOT), PROJECT_NAME,
        ],
        capture_output=True,
        text=True,
        errors="replace",
        shell=True,
    )

    summary = ""

    for line in result.stdout.splitlines():
        if line.startswith("RESULT "):
            summary = line

    return {
        "exit_code": result.returncode,
        "log_file": str(log_file),
        "summary": summary,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }




def run_behavioral_simulation(timeout_seconds=120) -> str:
    """Run behavioral simulation, filter the Vivado log, and return its path."""

    script_file = SCRIPT_DIR / "behav_sim.tcl"
    log_file = LOG_DIR / "behav_sim.log"

    if not script_file.is_file():
        raise FileNotFoundError(
            f"Missing Tcl script: {script_file}"
        )

    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Remove the previous simulation log to prevent stale results.
    if log_file.exists():
        log_file.unlink()

    try:
        result = subprocess.run(
            [
                "vivado",
                "-mode", "batch",
                "-source", str(script_file),
                "-log", str(log_file),
                "-tclargs", str(PROJECT_ROOT), PROJECT_NAME,
            ],
            capture_output=True,
            text=True,
            errors="replace",
            shell=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(
            f"Behavioral simulation timed out after {timeout_seconds} seconds."
        ) from exc

    if not log_file.is_file():
        raise FileNotFoundError(
            f"Simulation log not generated: {log_file}"
        )

    # Retain only testbench results and useful simulation diagnostics.
    patterns = [
        r"^ERROR:\s*.*",
        r"^ST_\d+:\s*(PASS|FAIL)$",
        r"^TESTS_PASSED:\s*\d+$",
        r"^TESTS_FAILED:\s*\d+$",
        r"^COVERAGE:\s*\d+(?:\.\d+)?%$",
        r"^RESULT status=.+",
        r"^FAILED_TEST id=.+",
        r"^SIM_ERROR\b.*",
        r"^SMOKE TEST FAILED$",
        r"^ALL TESTS PASSED$",
    ]
    pattern = re.compile("|".join(patterns))

    with log_file.open(encoding="utf-8", errors="replace") as log:
        selected_lines = [
            line.strip()
            for line in log
            if pattern.match(line.strip())
        ]

    # Make a failed Vivado process visible to the agent, even if
    # the Tcl script did not produce its own RESULT or SIM_ERROR line.
    if result.returncode != 0:
        selected_lines.append(
            f'SIM_ERROR reason="Vivado exited with code {result.returncode}"'
        )

    # Preserve the complete raw log if no expected diagnostics were found.
    if not selected_lines:
        raise RuntimeError(
            f"No recognizable simulation results found in: {log_file}"
        )

    # Back up the complete log before replacing it with the filtered version.
    backup_file = log_file.with_name(log_file.name + ".bak")
    shutil.copy2(log_file, backup_file)

    # Write through a temporary file to avoid a partially rewritten log.
    temp_file = log_file.with_name(log_file.name + ".tmp")
    try:
        temp_file.write_text(
            "\n".join(selected_lines) + "\n",
            encoding="utf-8",
        )
        temp_file.replace(log_file)
    finally:
        temp_file.unlink(missing_ok=True)

    return str(log_file)


def read_verilog(file_name: str) -> str:
    """Find and read the specified Verilog RTL file."""

    rtl_dir = PROJECT_ROOT / "rtl"

    if not file_name or "/" in file_name or "\\" in file_name:
        raise ValueError("Provide only the RTL filename.")

    files = [
        f for f in rtl_dir.rglob("*")
        if f.is_file() and f.name == file_name
        and f.resolve().is_relative_to(rtl_dir.resolve())
    ]

    if len(files) == 0:
        raise FileNotFoundError(f"RTL file not found: {file_name}")

    if len(files) > 1:
        raise ValueError("Multiple RTL files found.")

    return files[0].read_text(
        encoding="utf-8",
        errors="replace"
    )

def read_vivado_log(step: str) -> str:
    """Read a Vivado project-creation or behavioral-simulation log."""

    log_files = {
        "create_project": LOG_DIR / "build_project.log",
        "behavioral_simulation": LOG_DIR / "behav_sim.log",
    }

    if step not in log_files:
        raise ValueError(f"Invalid step: {step}")

    log_file = log_files[step]

    if not log_file.is_file():
        raise FileNotFoundError(
            f"Log file not found: {log_file}"
        )

    return log_file.read_text(
        encoding="utf-8",
        errors="replace",
    )


def check_constraints():

    script_file = SCRIPT_DIR / "check_constraints.tcl"

    log_file = LOG_DIR / "check_constraints.log"

    # Project is located inside the build directory.
    project_file = PROJECT_ROOT / "build" / f"{PROJECT_NAME}.xpr"

    if not script_file.is_file():
        raise FileNotFoundError(
            f"Missing Tcl script: {script_file}"
        )

    if not project_file.is_file():
        raise FileNotFoundError(
            f"Vivado project not found: {project_file}"
        )

    log_file.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "vivado",
            "-mode", "batch",
            "-source", str(script_file),
            "-log", str(log_file),
            "-tclargs", str(PROJECT_ROOT), PROJECT_NAME,
        ],
        capture_output=True,
        text=True,
        errors="replace",
        shell=True,
    )

    summary = ""
    missing_constraints = []

    for line in result.stdout.splitlines():

        if line.startswith("RESULT "):
            summary = line

        elif line.startswith("MISSING "):
            missing_constraints.append(line)

    return {
        "exit_code": result.returncode,
        "log_file": str(log_file),
        "summary": summary,
        "missing_constraints": missing_constraints,
        "stderr": result.stderr[-2000:] if result.returncode != 0 else "",
    }
    
def run_synthesis():

    script_file = SCRIPT_DIR / "run_synthesis.tcl"

    log_file = LOG_DIR / "run_synthesis.log"

    project_file = PROJECT_ROOT / "build" / f"{PROJECT_NAME}.xpr"

    if not script_file.is_file():
        raise FileNotFoundError(
            f"Missing Tcl script: {script_file}"
        )

    if not project_file.is_file():
        raise FileNotFoundError(
            f"Vivado project not found: {project_file}"
        )

    log_file.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "vivado",
            "-mode", "batch",
            "-source", str(script_file),
            "-log", str(log_file),
            "-tclargs", str(PROJECT_ROOT), PROJECT_NAME,
        ],
        capture_output=True,
        text=True,
        errors="replace",
        shell=True,
    )

    summary = ""
    filtered_log = ""

    for line in result.stdout.splitlines():

        if line.startswith("RESULT "):
            summary = line

        elif line.startswith("FILTERED_LOG:"):
            filtered_log = line.split(":", 1)[1].strip()

    return {
        "exit_code": result.returncode,
        "log_file": str(log_file),
        "summary": summary,
        "filtered_log": filtered_log,
        "stderr": result.stderr[-2000:] if result.returncode != 0 else "",
    }



    
def read_synthesis_log(log_type: str) -> str:
    """Read the last 2000 characters of a synthesis log."""

    logs = {
        "raw": PROJECT_ROOT / "build" / f"{PROJECT_NAME}.runs" / "synth_1" / "runme.log",
        "filtered": PROJECT_ROOT / "agent_reports" / "synth_filtered.log"
    }

    if log_type not in logs:
        raise ValueError("Log type must be 'raw' or 'filtered'.")

    log_file = logs[log_type]

    if not log_file.is_file():
        raise FileNotFoundError(
            f"Synthesis log not found: {log_file}"
        )

    content = log_file.read_text(
        encoding="utf-8",
        errors="replace"
    )

    return content[-2000:]



    
def check_device_part():

    script_file = SCRIPT_DIR / "check_device_part.tcl"

    log_file = LOG_DIR / "check_device_part.log"

    # Vivado project is inside the build directory.
    project_file = PROJECT_ROOT / "build" / f"{PROJECT_NAME}.xpr"

    if not script_file.is_file():
        raise FileNotFoundError(
            f"Missing Tcl script: {script_file}"
        )

    if not project_file.is_file():
        raise FileNotFoundError(
            f"Vivado project not found: {project_file}"
        )

    log_file.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "vivado",
            "-mode", "batch",
            "-source", str(script_file),
            "-log", str(log_file),
            "-tclargs", str(PROJECT_ROOT), PROJECT_NAME,
        ],
        capture_output=True,
        text=True,
        errors="replace",
        shell=True,
    )

    summary = ""

    for line in result.stdout.splitlines():
        if line.startswith("RESULT "):
            summary = line

    return {
        "exit_code": result.returncode,
        "log_file": str(log_file),
        "summary": summary,
        "stderr": result.stderr[-2000:] if result.returncode != 0 else "",
    }   
    
    
def read_synthesis_diagnostics() -> dict:
    """Read filtered synthesis errors and warnings."""

    log_file = LOG_DIR / "synth_filtered.log"

    if not log_file.is_file():
        raise FileNotFoundError(
            f"Synthesis log not found: {log_file}"
        )

    # Read filtered synthesis diagnostics.
    content = log_file.read_text(
        encoding="utf-8",
        errors="replace"
    ).strip()

    # Create summary for the agent.
    summary = "RESULT stage=synthesis_diagnostics status=SUCCESS"

    if content:
        summary += "\n" + content

    return {
        "exit_code": 0,
        "summary": summary,
        "log_file": str(log_file),
    }
    
    
    
# Manual testing of Vivado tools.

if __name__ == "__main__":

    steps = [
        "create_project",
        "behavioral_simulation"
    ]

    for step in steps:

        print(f"\n========== {step.upper()} ==========\n")

        try:
            log_content = read_vivado_log(step)
        except (OSError, ValueError) as exc:
            log_content = str(exc)

        print(log_content)

        print(f"\n========== END OF {step.upper()} ==========\n")
