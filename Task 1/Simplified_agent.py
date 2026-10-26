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
    saved_results = {}

    # Give the agent its task.
    request = {
        "agent": AGENT_ID,
        "environment": "remote",
        "tools": tool_descriptions,
        "input": (
            "Create or open the Vivado project and investigate its warnings. "
            "Read actual warning messages and build_project.tcl before editing. "
            "Correct relevant causes only in build_project.tcl. "
            "Preserve the intended target device and design files. "
            "Do not suppress warnings just to reduce their count. "
            "Rerun after changes, compare warning counts, and report the result."
        ),
    }

    for request_number in range(1, MAX_API_REQUESTS + 1):

        # Send the task or previous tool results to the agent.
        response = client.interactions.create(
            **request,
            agent_config={
                "type": "antigravity",
                "max_total_tokens": 10_000,
            },
            timeout=120.0,
        )

        # Stop when the task is complete.
        if response.status == "completed":
            print(response.output_text or "Agent task completed.")
            return

        if response.status != "requires_action":
            raise RuntimeError(
                f"Agent stopped with status: {response.status}"
            )

        if request_number == MAX_API_REQUESTS:
            raise RuntimeError(
                "API request limit reached; task is incomplete."
            )

        steps = response.steps

        if steps is None:
            steps = []

        # Find calls that already have a result.
        answered_ids = set()

        for step in steps:
            if step.type == "function_result":
                answered_ids.add(step.call_id)

        # Find calls that still need a result.
        pending_calls = []

        for step in steps:
            if step.type == "function_call":
                if step.id not in answered_ids:
                    pending_calls.append(step)

        if len(pending_calls) == 0:
            raise RuntimeError("Agent supplied no pending tool calls.")

        # Execute pending calls and collect their results.
        function_results = []

        for call in pending_calls:

            # Reuse the result if this exact call was executed earlier.
            if call.id in saved_results:
                result = saved_results[call.id]

            else:
                try:
                    # Read the arguments provided by the agent.
                    arguments = call.arguments

                    if arguments is None:
                        arguments = {}

                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)

                    # Limit the total number of tool executions.
                    if tool_call_count >= MAX_TOOL_CALLS:
                        raise RuntimeError(
                            "Local tool-call limit reached."
                        )

                    tool_call_count += 1

                    # Limit script-edit attempts.
                    if call.name == "edit_project_script":
                        if edit_attempts >= MAX_EDIT_ATTEMPTS:
                            raise RuntimeError(
                                "Script-edit limit reached."
                            )

                        edit_attempts += 1

                    # Avoid sending repeated log examples.
                    if call.name == "summarize_vivado_log":
                        arguments["max_messages"] = 0

                    # Find and execute the requested Python function.
                    function = available_functions[call.name] ## Function name, such as "edit_project_script"
                    result = function(**arguments)

                    # Reduce the amount of Vivado output sent back.
                    if call.name == "create_project":
                        result = dict(result)

                        for field in ("stdout", "stderr"):
                            if result["exit_code"] == 0:
                                result.pop(field, None)

                            elif isinstance(result.get(field), str):
                                result[field] = result[field][-3000:]

                except Exception as error:
                    result = {
                        "tool_failed": True,
                        "error": str(error),
                    }

                saved_results[call.id] = result  # Unique ID identifying this particular request

            # Attach the result to its original call ID.
            function_results.append({
                "type": "function_result",
                "name": call.name,
                "call_id": call.id,
                "result": result,
            })

        # Prepare the next request with the tool results.
        request = {
            "agent": AGENT_ID,
            "previous_interaction_id": response.id,
            "environment": (
                response.environment_id or request["environment"]
            ),
            "tools": tool_descriptions,
            "input": function_results,
        }


if __name__ == "__main__":
    main()