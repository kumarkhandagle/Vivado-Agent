from google import genai
import json
import vivado_tools


AGENT_ID = "antigravity-preview-09-2026"

# Local execution limits.
MAX_API_REQUESTS = 12
MAX_TOOL_CALLS = 12
MAX_EDIT_ATTEMPTS = 3

# Best-effort API budget per request.
# Includes input, output, and thinking; excludes cached tokens.
MAX_TOKENS_PER_REQUEST = 10_000


# Map tool names to local functions.
available_functions = {
    "create_project": vivado_tools.create_project,
    "summarize_vivado_log": vivado_tools.summarize_vivado_log,
    "read_project_script": vivado_tools.read_project_script,
    "edit_project_script": vivado_tools.edit_project_script,
}


# Describe the available functions to Antigravity.
tool_descriptions = [
    {
        "type": "function",
        "name": "create_project",
        "description": (
            "Create or open the local Vivado project by running "
            "build_project.tcl. Returns the exit code and log path. "
            "On failure, also returns truncated stdout and stderr. "
            "Use summarize_vivado_log to inspect warnings."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "summarize_vivado_log",
        "description": (
            "Return severity totals and messages grouped by severity "
            "and ID, with counts, summaries, and one complete "
            "representative example per group. Additional examples "
            "are disabled locally to reduce token usage."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "log_file": {
                    "type": "string",
                    "description": "Path to the Vivado log file.",
                },
                "filter": {
                    "type": "string",
                    "enum": [
                        "errors",
                        "warnings",
                        "critical",
                        "info",
                        "all",
                        "default",
                    ],
                    "description": (
                        "Default includes errors, critical warnings, "
                        "and warnings."
                    ),
                },
                "max_messages": {
                    "type": ["integer", "null"],
                    "minimum": 0,
                    "description": (
                        "Additional examples per severity. "
                        "Python always overrides this to zero. "
                        "Each group still retains one full example."
                    ),
                },
            },
            "required": ["log_file"],
        },
    },
    {
        "type": "function",
        "name": "read_project_script",
        "description": (
            "Read build_project.tcl. Returns the script path, "
            "complete contents, and line count."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "edit_project_script",
        "description": (
            "Replace one exact occurrence of old_text with new_text "
            "in build_project.tcl. Creates a backup first. "
            "Rejects missing or ambiguous matches. "
            "Permitted only for project-setup corrections. "
            "Preserve the intended target device and design files."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "old_text": {
                    "type": "string",
                    "description": (
                        "Exact existing text identifying one location."
                    ),
                },
                "new_text": {
                    "type": "string",
                    "description": (
                        "Replacement Tcl text. Empty deletes the match."
                    ),
                },
            },
            "required": ["old_text", "new_text"],
        },
    },
]


def main():
    client = genai.Client()

    tool_call_count = 0
    edit_attempts = 0

    # Prevent repeated execution of the same call ID.
    local_results = {}

    request = {
        "agent": AGENT_ID,
        "input": (
            "Create or open the Vivado project and investigate its warnings. "
            "Inspect representative message text and the Tcl script before "
            "deciding which warnings need correction. "
            "Correct relevant causes within build_project.tcl, preserving "
            "the intended target device and design files. "
            "Do not suppress warnings merely to reduce their count. "
            "Rerun after changes and compare warning counts. "
            "Report warnings resolved and explain any remaining warnings "
            "or corrections outside the permitted script. "
            "Use the supplied local tools and keep the final report concise."
        ),
        "environment": "remote",
        "tools": tool_descriptions,
    }

    for request_number in range(1, MAX_API_REQUESTS + 1):
        print(
            f"\nSending API request "
            f"{request_number}/{MAX_API_REQUESTS}...",
            flush=True,
        )

        response = client.interactions.create(
            **request,
            agent_config={
                "type": "antigravity",
                "max_total_tokens": MAX_TOKENS_PER_REQUEST,
            },
            timeout=120.0,
        )

        print("Agent status:", response.status)

        # Print the complete usage breakdown.
        usage = getattr(response, "usage", None)

        if usage is not None:
            print("Token usage:", usage)

        if response.output_text:
            print(response.output_text)

        if response.status == "completed":
            print("\nAgent task finished.")
            print("Local tool calls:", tool_call_count)
            print("Script-edit attempts:", edit_attempts)
            return

        if response.status == "incomplete":
            print(
                "\nAgent stopped before completion, possibly because "
                "the token budget was reached."
            )
            print("Interaction ID:", response.id)
            print("No automatic continuation will be sent.")
            print("Local tool calls:", tool_call_count)
            print("Script-edit attempts:", edit_attempts)
            return

        if response.status != "requires_action":
            print(
                "\nStopped because the agent returned status:",
                response.status,
            )
            return

        steps = response.steps or []

        # Exclude calls already answered in the interaction.
        executed_call_ids = {
            step.call_id
            for step in steps
            if step.type == "function_result"
        }

        pending_calls = [
            step
            for step in steps
            if step.type == "function_call"
            and step.id not in executed_call_ids
        ]

        if not pending_calls:
            print("No pending function calls were found.")
            return

        # Do not execute tools when their results cannot be returned.
        if request_number == MAX_API_REQUESTS:
            print("\nAPI request limit reached.")
            print(
                "Pending tools:",
                ", ".join(call.name for call in pending_calls),
            )
            print("No further tools executed.")
            print("Agent task remains incomplete.")
            return

        function_results = []

        for call in pending_calls:
            function_name = call.name

            print("\nRequested tool:", function_name)

            if call.id in local_results:
                result = local_results[call.id]
                print("Returning the previously recorded result.")

            else:
                try:
                    if function_name not in available_functions:
                        raise ValueError(
                            f"Unknown local tool: {function_name}"
                        )

                    if tool_call_count >= MAX_TOOL_CALLS:
                        raise ValueError(
                            "Local tool-call limit reached."
                        )

                    arguments = call.arguments

                    # Accept a dictionary or JSON-encoded arguments.
                    if arguments is None:
                        arguments = {}
                    elif isinstance(arguments, str):
                        arguments = json.loads(arguments)

                    if not isinstance(arguments, dict):
                        raise ValueError(
                            "Tool arguments must be a dictionary."
                        )

                    # Copy before applying local argument limits.
                    arguments = dict(arguments)

                    tool_call_count += 1

                    if function_name == "edit_project_script":
                        if edit_attempts >= MAX_EDIT_ATTEMPTS:
                            raise ValueError(
                                "Project-script edit limit reached."
                            )

                        edit_attempts += 1

                    # Keep counts and one example per group,
                    # but omit repeated additional examples.
                    if function_name == "summarize_vivado_log":
                        arguments["max_messages"] = 0

                    print("Executing locally...", flush=True)

                    function = available_functions[function_name]
                    result = function(**arguments)

                    if function_name == "create_project":
                        result = dict(result)

                        if result["exit_code"] == 0:
                            # Inspect warnings through the summary tool.
                            result.pop("stdout", None)
                            result.pop("stderr", None)
                        else:
                            # Retain failure evidence, including
                            # unprefixed Tcl errors missed by the parser.
                            for field in ("stdout", "stderr"):
                                output = result.get(field, "")

                                if len(output) > 3000:
                                    result[field] = output[-3000:]
                                    result[field + "_truncated"] = True

                    print("Tool execution returned.")

                except Exception as error:
                    result = {
                        "tool_failed": True,
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }

                    print("Tool failed:", error)

                local_results[call.id] = result

            function_results.append({
                "type": "function_result",
                "name": function_name,
                "call_id": call.id,
                "result": result,
            })

        # Continue with local tool results.
        # The API call above reapplies the token budget each time.
        request = {
            "agent": AGENT_ID,
            "previous_interaction_id": response.id,
            "environment": (
                response.environment_id or request["environment"]
            ),
            "input": function_results,
            "tools": tool_descriptions,
        }


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Agent execution stopped:", error)