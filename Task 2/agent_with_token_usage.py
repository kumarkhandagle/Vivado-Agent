"""Run the existing agent workflow using tools discovered through MCP.

Requires the official MCP Python SDK v2. Run with --list-tools to test
the MCP connection without sending requests to the agent API.
"""

import argparse
import asyncio
import json
import os
import sys
import traceback
from pathlib import Path

from google import genai
from mcp import Client as MCPClient, StdioServerParameters
from mcp.types import TextContent


AGENT_ID = "antigravity-preview-09-2026"

MAX_API_REQUESTS = 20
MAX_TOOL_CALLS = 12
MAX_EDIT_ATTEMPTS = 5
MAX_TOKENS_PER_REQUEST = 10_000

# Allows time for a local Vivado batch run.
# This is separate from the agent API timeout.
MCP_TIMEOUT_SECONDS = 600.0


def unpack_mcp_result(mcp_result):
    """Extract the dictionary returned by our Vivado MCP tools."""

    # Failed calls can contain their error message as text.
    if mcp_result.is_error:
        text_parts = []

        for block in mcp_result.content:
            if isinstance(block, TextContent):
                text_parts.append(block.text)

        message = "\n".join(text_parts)

        raise RuntimeError(
            message or "MCP tool execution failed."
        )

    # Some MCP tools return structured data directly.
    result = mcp_result.structured_content
    if isinstance(result, dict):
        return result

    # Our MCP server currently returns dictionaries as JSON text.
    for block in mcp_result.content:
        if isinstance(block, TextContent):
            try:
                result = json.loads(block.text)
            except json.JSONDecodeError:
                continue

            if isinstance(result, dict):
                return result

    raise ValueError(
        "MCP tool did not return a dictionary as structured data or JSON text."
    )



def print_token_usage(response):
    """Print total tokens consumed by an API interaction."""

    usage = getattr(response, "usage", None)

    if usage is None:
        print("Token usage: not available.")
        return

    total = getattr(usage, "total_tokens", None)

    if total is not None:
        print(f"Total tokens: {total:,}")
    else:
        print("Total tokens: not available.")



async def run_agent(mcp_client, tool_descriptions):
    tool_call_count = 0
    edit_attempts = 0
    saved_results = {}

    available_names = {
        tool["name"]
        for tool in tool_descriptions
    }

    # Give the agent its task and the discovered tool descriptions.
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

    with genai.Client() as client:
        for request_number in range(1, MAX_API_REQUESTS + 1):
            print(
                f"\nSending API request "
                f"{request_number}/{MAX_API_REQUESTS}...",
                flush=True,
            )

            # Keep the MCP event loop running while the synchronous API waits.
            response = await asyncio.to_thread(
                client.interactions.create,
                **request,
                agent_config={
                    "type": "antigravity",
                    "max_total_tokens": MAX_TOKENS_PER_REQUEST,
                },
                timeout=120.0,
            )

            print("Agent status:", response.status)
            print_token_usage(response)

            # Stop when the task is complete.
            if response.status == "completed":
                print(response.output_text or "Agent task completed.")
                print("Local tool calls:", tool_call_count)
                print("Script-edit attempts:", edit_attempts)
                return

            # When the agent reaches its token budget, continue the
            # same interaction rather than stopping the Python program.
            if response.status == "incomplete":
                if request_number == MAX_API_REQUESTS:
                    raise RuntimeError(
                        "API request limit reached after incomplete response. "
                        f"Interaction ID: {response.id}"
                    )

                print("Agent interaction incomplete; continuing...")
                request = {
                    "agent": AGENT_ID,
                    "previous_interaction_id": response.id,
                    "environment": (
                        response.environment_id or request["environment"]
                    ),
                    "tools": tool_descriptions,
                    "input": "continue",
                }
                continue

            if response.status != "requires_action":
                raise RuntimeError(
                    f"Agent stopped with status: {response.status}. "
                    f"Interaction ID: {response.id}"
                )

            # Do not execute tools when another API request
            # cannot return their results.
            if request_number == MAX_API_REQUESTS:
                raise RuntimeError(
                    "API request limit reached; task is incomplete. "
                    "No further tools executed."
                )

            steps = response.steps or []

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
                raise RuntimeError(
                    "Agent supplied no pending tool calls."
                )

            # Execute pending calls and collect their results.
            function_results = []

            for call in pending_calls:
                print(
                    "\nRequested tool:",
                    call.name,
                    flush=True,
                )

                # Reuse the result if this exact call was executed earlier.
                if call.id in saved_results:
                    result = saved_results[call.id]
                    print("Returning the previously saved result.")

                else:
                    try:
                        # Check that the tool was discovered from the server.
                        if call.name not in available_names:
                            raise ValueError(
                                f"Unknown MCP tool: {call.name}"
                            )

                        # Read the arguments provided by the agent.
                        arguments = call.arguments

                        if arguments is None:
                            arguments = {}

                        elif isinstance(arguments, str):
                            arguments = json.loads(arguments)

                        if not isinstance(arguments, dict):
                            raise ValueError(
                                "Tool arguments must be a dictionary."
                            )

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

                        # Ask the MCP server to execute the requested tool.
                        # This replaces the available_functions lookup.
                        mcp_result = await mcp_client.call_tool(
                            call.name,
                            arguments,
                        )

                        # Extract the original dictionary from the response.
                        result = unpack_mcp_result(mcp_result)

                        print("MCP tool execution returned.")

                    except Exception as error:
                        result = {
                            "tool_failed": True,
                            "error": str(error),
                        }

                        print("Tool failed:", error)

                    # Remember the result using this specific call's ID.
                    saved_results[call.id] = result

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


async def main(list_only=False):
    # Locate the MCP server beside this agent.py file.
    script_dir = Path(__file__).resolve().parent
    server_file = script_dir / "vivado_tool_mcp.py"

    if not server_file.is_file():
        raise FileNotFoundError(
            f"MCP server script not found: {server_file}"
        )

    # Describe how the client should launch the local server.
    server = StdioServerParameters(
        command=sys.executable,
        args=["-u", str(server_file)],
        cwd=str(script_dir),

        # Preserve Vivado, PATH, and license settings
        # for our own local server.
        env=os.environ.copy(),
    )

    # Entering this block starts the server.
    # Leaving it shuts the server down.
    async with MCPClient(
        server,
        read_timeout_seconds=MCP_TIMEOUT_SECONDS,
    ) as mcp_client:

        # Discover the registered tools.
        listed_tools = await mcp_client.list_tools()

        tool_descriptions = []

        # Convert MCP tool definitions into the agent API's format.
        for tool in listed_tools.tools:
            tool_descriptions.append({
                "type": "function",
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            })

        if not tool_descriptions:
            raise RuntimeError(
                "The MCP server supplied no tools."
            )

        print("Connected to the Vivado MCP server.")
        print("Discovered tools:")

        for tool in tool_descriptions:
            print(" -", tool["name"])

        # Optional connection test without agent API requests.
        if list_only:
            print(
                "\nConnection verified. "
                "No agent API requests sent."
            )
            return

        # Begin the agent request/tool-result loop.
        await run_agent(mcp_client, tool_descriptions)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="Test MCP discovery without calling the agent API.",
    )

    options = parser.parse_args()

    try:
        asyncio.run(
            main(list_only=options.list_tools)
        )

    except KeyboardInterrupt:
        print(
            "\nStopped by the user.",
            file=sys.stderr,
        )
        sys.exit(130)

    except Exception as error:
        print("Agent execution stopped:", error, file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)