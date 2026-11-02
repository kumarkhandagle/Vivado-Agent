import pathlib
import subprocess
import datetime
import re


# 1. Run the project-creation Tcl script.
def create_project():
    script_file = pathlib.Path(
        r"C:/Agents/Day7/scripts/build_project.tcl"
    )

    log_file = pathlib.Path(
        r"C:/Agents/Day7/logs/build_project.log"
    )

    if not script_file.is_file():
        raise FileNotFoundError(f"Missing Tcl script: {script_file}")

    log_file.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "vivado",
            "-mode", "batch",
            "-source", str(script_file),
            "-log", str(log_file),
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
def summarize_vivado_log(log_file, filter="default", max_messages=None):
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
    script_file = pathlib.Path(
        r"C:/Agents/Day7/scripts/build_project.tcl"
    )

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
    script_file = pathlib.Path(
        r"C:/Agents/Day7/scripts/build_project.tcl"
    )

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



def update_verilog(file_path, old_text, new_text):

    with open(file_path, "r") as file:
        code = file.read()

    if not old_text:
        raise ValueError("old_text cannot be empty.")

    if code.count(old_text) != 1:
        raise ValueError(
            "old_text must appear exactly once in the file."
        )

    code = code.replace(old_text, new_text, 1)

    with open(file_path, "w") as file:
        file.write(code)

    return str(file_path)



def refresh_filesets():

    script_file = pathlib.Path(
        r"C:/Agents/Day7/scripts/refresh_fileset.tcl"
    )

    log_file = pathlib.Path(
        r"C:/Agents/Day7/logs/refresh_fileset.log"
    )

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




def run_behavioral_simulation(timeout_seconds=120):

    script_file = pathlib.Path(
        r"C:/Agents/Day7/scripts/behav_sim.tcl"
    )

    log_file = pathlib.Path(
        r"C:/Agents/Day7/logs/behav_sim.log"
    )

    if not script_file.is_file():
        raise FileNotFoundError(
            f"Missing Tcl script: {script_file}"
        )

    log_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                "vivado",
                "-mode", "batch",
                "-source", str(script_file),
                "-log", str(log_file),
            ],
            capture_output=True,
            text=True,
            errors="replace",
            shell=True,
            timeout=timeout_seconds,
        )

    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "passed": -1,
            "failed": -1,
            "coverage": None,
            "log_file": str(log_file),
        }

    # Find Tcl result in Vivado output
    summary = ""

    for line in result.stdout.splitlines():
        if line.strip().startswith("RESULT "):
            summary = line.strip()

    # Read log if result is missing from stdout
    if not summary and log_file.exists():
        for line in log_file.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if line.strip().startswith("RESULT "):
                summary = line.strip()

    # Extract values from result
    values = dict(
        re.findall(r"(\w+)=([^\s]+)", summary)
    )

    coverage_text = values.get("coverage", "NA").rstrip("%")

    try:
        coverage = float(coverage_text)
    except ValueError:
        coverage = None

    status = values.get("status", "ERROR")

    if result.returncode != 0:
        status = "ERROR"

    return {
        "exit_code": result.returncode,
        "status": status,
        "passed": int(values.get("passed", -1)),
        "failed": int(values.get("failed", -1)),
        "coverage": coverage,
        "log_file": str(log_file),
        "summary": summary,
        "error": result.stderr[-2000:] if status == "ERROR" else "",
    }







# Manual testing of Vivado tools.
# This block will not execute when imported by the MCP server.
if __name__ == "__main__":

    try:
        # 1. Create or open the Vivado project
        print("\n1. Creating Vivado Project")

        project_result = create_project()

        print("Exit Code:", project_result["exit_code"])
        print("Log File:", project_result["log_file"])

        if project_result["exit_code"] != 0:
            raise RuntimeError("Project creation failed.")

        # 2. Summarize Vivado warnings and errors
        print("\n2. Analyzing Vivado Log")

        summary = summarize_vivado_log(
            project_result["log_file"],
            filter="default",
            max_messages=3
        )

        for group in summary["groups"]:
            print(
                f"{group['severity']} | "
                f"{group['id']} | "
                f"{group['count']} | "
                f"{group['summary']}"
            )

        print("Totals:", summary["totals"])

        # 3. Refresh RTL, testbench and XDC filesets
        print("\n3. Refreshing Vivado Filesets")

        refresh_result = refresh_filesets()

        print("Exit Code:", refresh_result["exit_code"])
        print("Summary:", refresh_result["summary"])

        if refresh_result["exit_code"] != 0:
            raise RuntimeError("Fileset refresh failed.")

        # 4. Run behavioral simulation
        print("\n4. Running Behavioral Simulation")

        sim_result = run_behavioral_simulation(
            timeout_seconds=120
        )

        print("Status:", sim_result["status"])
        print("Tests Passed:", sim_result["passed"])
        print("Tests Failed:", sim_result["failed"])
        print("Coverage:", sim_result["coverage"])
        print("Log File:", sim_result["log_file"])

        if sim_result["status"] == "PASS":
            print("Simulation completed successfully.")
        else:
            print("Simulation did not meet the pass criteria.")
            print("Details:", sim_result.get("error", ""))

    except (OSError, ValueError, RuntimeError) as error:
        print("Operation failed:", error)
