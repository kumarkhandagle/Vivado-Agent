
"""Simple Antigravity agent using a local Vivado MCP server."""

import asyncio
import json
import sys
from pathlib import Path

from google import genai
from mcp import Client, StdioServerParameters
from mcp.types import TextContent


AGENT_ID = "antigravity-preview-09-2026"

MCP_DIRECTORY = Path(r"C:\Agents\Day6")
MCP_SCRIPT = MCP_DIRECTORY / "vivado_tool_mcp.py"

MAX_API_REQUESTS = 20
MAX_TOOL_CALLS = 16
MAX_EDIT_ATTEMPTS = 3
MAX_TOKENS_PER_REQUEST = 10_000


def get_result(reply):
    """Extract a dictionary from an MCP tool response."""

    if reply.is_error:
        raise RuntimeError(str(reply.content))

    if isinstance(reply.structured_content, dict):
        return reply.structured_content

    # MCP tools may return JSON as text.
    for block in reply.content:

        if isinstance(block, TextContent):

            try:
                data = json.loads(block.text)
            except json.JSONDecodeError:
                continue

            if isinstance(data, dict):
                return data

    raise ValueError("MCP tool did not return a JSON dictionary")


async def main():

    # Step 1: Configure the local MCP server.
    if not MCP_SCRIPT.is_file():
        raise FileNotFoundError(
            f"MCP server not found: {MCP_SCRIPT}"
        )

    server = StdioServerParameters(
        command=sys.executable,
        args=[str(MCP_SCRIPT)],
        cwd=str(MCP_DIRECTORY),
    )

    async with Client(
        server,
        read_timeout_seconds=600.0
    ) as mcp:

        # Step 2: Discover registered MCP tools.
        discovered = (await mcp.list_tools()).tools

        tools = []
        allowed_tools = set()

        for tool in discovered:

            tools.append({
                "type": "function",
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            })

            allowed_tools.add(tool.name)

        if not tools:
            raise RuntimeError("No MCP tools found")

        print("Discovered tools:", sorted(allowed_tools))

        # Step 3: Prepare the first LLM request.
        request = {
            "agent": AGENT_ID,
            "environment": "remote",
            "tools": tools,
            "input": (
                "Run Vivado, read build_project.tcl and inspect warnings. "
                "Correct only safe project-setup problems in build_project.tcl. "
                "Preserve the FPGA part and design files; never suppress warnings. "
                "Do not summarize an unchanged log repeatedly. "
                "After each edit, rerun Vivado and summarize the new log. "
                "Do not report success without checking the final log."
            ),
        }

        tool_calls = 0
        edit_attempts = 0
        saved_results = {}

        # Step 4: Communicate with Antigravity.
        with genai.Client() as client:

            for number in range(1, MAX_API_REQUESTS + 1):

                print(
                    f"\nAPI request {number}/{MAX_API_REQUESTS}"
                )

                response = await asyncio.to_thread(
                    client.interactions.create,
                    **request,
                    agent_config={
                        "type": "antigravity",
                        "max_total_tokens": MAX_TOKENS_PER_REQUEST,
                    },
                    timeout=600.0,
                )

                print("Status:", response.status)

                usage = getattr(response, "usage", None)

                if usage is not None:
                    print(
                        "Total tokens:",
                        getattr(usage, "total_tokens", "N/A")
                    )

                # Agent completed its task.
                if response.status == "completed":
                    print(
                        "Agent report (not independently verified):"
                    )
                    print(
                        response.output_text or "No final report"
                    )
                    break

                if number == MAX_API_REQUESTS:
                    print("API request limit reached. Stopping.")
                    break

                environment = (
                    response.environment_id
                    or request["environment"]
                )

                # Continue if the token budget was exhausted.
                if response.status == "incomplete":

                    print(
                        "Interaction token budget reached. Continuing."
                    )

                    request = {
                        "agent": AGENT_ID,
                        "previous_interaction_id": response.id,
                        "environment": environment,
                        "tools": tools,
                        "input": "continue",
                    }

                    continue

                if response.status != "requires_action":
                    print(
                        f"Agent ended with status "
                        f"{response.status!r}. Stopping."
                    )
                    break

                # Step 5: Find pending function calls.
                steps = response.steps or []

                answered = {
                    step.call_id
                    for step in steps
                    if step.type == "function_result"
                }

                pending = [
                    step
                    for step in steps
                    if (
                        step.type == "function_call"
                        and step.id not in answered
                    )
                ]

                if not pending:
                    print("No pending MCP calls. Stopping.")
                    break

                # Check limits before executing the batch.
                new_calls = [
                    call
                    for call in pending
                    if call.id not in saved_results
                ]

                if tool_calls + len(new_calls) > MAX_TOOL_CALLS:
                    print(
                        "Insufficient tool-call budget. Stopping."
                    )
                    break

                new_edits = sum(
                    call.name == "edit_project_script"
                    for call in new_calls
                )

                if (
                    edit_attempts + new_edits
                    > MAX_EDIT_ATTEMPTS
                ):
                    print(
                        "Insufficient Tcl edit budget. Stopping."
                    )
                    break

                function_results = []
                stop = False

                # Step 6: Execute functions through MCP.
                for call in pending:

                    if call.id in saved_results:
                        result = saved_results[call.id]

                    else:

                        if tool_calls >= MAX_TOOL_CALLS:
                            print(
                                "Tool-call limit reached. Stopping."
                            )
                            stop = True
                            break

                        if (
                            call.name == "edit_project_script"
                            and edit_attempts >= MAX_EDIT_ATTEMPTS
                        ):
                            print(
                                "Tcl edit limit reached. Stopping."
                            )
                            stop = True
                            break

                        try:

                            if call.name not in allowed_tools:
                                raise ValueError(
                                    "Unknown tool: " + call.name
                                )

                            arguments = call.arguments or {}

                            if isinstance(arguments, str):
                                arguments = json.loads(arguments)

                            if not isinstance(arguments, dict):
                                raise ValueError(
                                    "Invalid tool arguments"
                                )

                            tool_calls += 1

                            if call.name == "edit_project_script":
                                edit_attempts += 1

                            reply = await mcp.call_tool(
                                call.name,
                                arguments
                            )

                            result = get_result(reply)

                        except Exception as error:

                            result = {
                                "tool_failed": True,
                                "error": str(error),
                            }

                        saved_results[call.id] = result

                    print(
                        "Tool:", call.name,
                        "Result:", str(result)[:400]
                    )

                    function_results.append({
                        "type": "function_result",
                        "name": call.name,
                        "call_id": call.id,
                        "result": result,
                        "is_error": bool(
                            result.get("tool_failed", False)
                        ),
                    })

                # Prevent incomplete function-result batches.
                if stop:
                    print(
                        "Agent stopped due to execution limits."
                    )
                    break

                # Step 7: Return tool results to Antigravity.
                request = {
                    "agent": AGENT_ID,
                    "previous_interaction_id": response.id,
                    "environment": environment,
                    "tools": tools,
                    "input": function_results,
                }

        print("\nAgent tool calls:", tool_calls)
        print("Edit attempts:", edit_attempts)


if __name__ == "__main__":
    asyncio.run(main())
