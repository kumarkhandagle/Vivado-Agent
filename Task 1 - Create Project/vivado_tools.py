import pathlib
import subprocess
import datetime


# 1. Run the project-creation Tcl script.
def create_project():
    script_file = pathlib.Path(
        r"C:/Agents/Day5/scripts/build_project.tcl"
    )

    log_file = pathlib.Path(
        r"C:/Agents/Day5/logs/build_project.log"
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
        r"C:/Agents/Day5/scripts/build_project.tcl"
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
        r"C:/Agents/Day5/scripts/build_project.tcl"
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


# Manual test: create/open the project and summarize its log.
# Importing this file from agent.py will skip this block.
if __name__ == "__main__":
    try:
        print("Running project setup...", flush=True)

        project_result = create_project()

        print("Exit code:", project_result["exit_code"])
        print("Log file:", project_result["log_file"])

        if project_result["exit_code"] != 0:
            print(project_result["stdout"])

        if project_result["stderr"]:
            print(project_result["stderr"])

        summary = summarize_vivado_log(
            project_result["log_file"],
            filter="default",
            max_messages=3,
        )

        print("\nSeverity | Message ID | Count | Summary")

        for group in summary["groups"]:
            print(
                f"{group['severity']} | {group['id']} | "
                f"{group['count']} | {group['summary']}"
            )

        print("\nTotals:", summary["totals"])
        print("Omitted additional examples:", summary["omitted_examples"])

    except (OSError, ValueError) as error:
        print("Operation failed:", error)