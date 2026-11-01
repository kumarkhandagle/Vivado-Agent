"""Run goal-driven Vivado MCP workflows using skills/vivado-flow/SKILL.md."""

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
MAX_API_REQUESTS = 30
MAX_TOOL_CALLS = 20
MAX_TOKENS_PER_REQUEST = 20_000
MCP_TIMEOUT_SECONDS = 600.0

# MCP tools available to the skill-guided agent (no RTL editing tools).
ALLOWED_MCP_TOOLS = {
    "create_project",
    "read_project_script",
    "run_behavioral_simulation",
    "read_vivado_log",
    "read_verilog",
    "refresh_filesets",
    "check_device_part",
    "check_constraints",
    "run_synthesis",
    "read_synthesis_diagnostics",
    "run_implementation",
    "read_implementation_diagnostics",
    "analyze_timing",
    "read_timing_details",
    "analyze_resources",
    "generate_bitstream",
}


class AgentLimitReached(RuntimeError):
    """Stop instead of looping indefinitely on tool requests."""


def unpack_mcp_result(mcp_result):
    """Extract structured content, or fall back to text from MCP."""
    blocks = [
        block.text for block in (mcp_result.content or [])
        if isinstance(block, TextContent)
    ]
    if mcp_result.is_error:
        raise RuntimeError("\n".join(blocks) or "MCP tool execution failed.")
    if mcp_result.structured_content is not None:
        return mcp_result.structured_content
    if not blocks:
        raise ValueError("MCP tool returned no usable result.")
    text = "\n".join(blocks)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def print_token_usage(response):
    usage = getattr(response, "usage", None)
    total = getattr(usage, "total_tokens", None) if usage else None
    print(
        f"Total tokens: {total:,}" if total is not None
        else "Token usage: not available."
    )


def format_tool_result(payload):
    """Keep the short, useful fields from a standardized MCP response."""
    if not isinstance(payload, dict):
        return {"tool_failed": True, "error": f"Unexpected MCP result: {payload!r}"}

    # The tool_response() helper wraps the Python tool result under 'data'.
    result = payload.get("data", payload)
    if not isinstance(result, dict):
        return {"tool_failed": True, "error": "MCP data is not a dictionary."}

    compact = {
        "exit_code": result.get("exit_code"),
        "summary": result.get("summary", ""),
    }
    for key in ("missing_constraints", "filtered_log", "log_file",
                "content", "bit_file", "report_file", "file_path"):
        if key in result:
            compact[key] = result[key]

    # Preserve a short error if a subprocess fails before printing RESULT.
    if result.get("exit_code") != 0:
        stderr = result.get("stderr", "")
        if stderr:
            compact["stderr"] = str(stderr)[-1500:]

    if payload.get("status") in ("FAILED", "ERROR"):
        compact["tool_failed"] = True
        compact["error"] = payload.get("message", "MCP tool reported failure.")
    return compact




async def run_agent(mcp_client, tool_descriptions, task):
    tool_call_count = 0
    saved_results = {}
    available_names = {tool["name"] for tool in tool_descriptions}

    request = {
        "agent": AGENT_ID,
        "environment": "remote",
        "tools": tool_descriptions,
        "input": task,
    }

    with genai.Client() as client:
        for request_number in range(1, MAX_API_REQUESTS + 1):
            print(f"\nSending API request {request_number}/{MAX_API_REQUESTS}...", flush=True)
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

            if response.status == "completed":
                print(response.output_text or "Agent task completed.")
                print("Local tool calls:", tool_call_count)
                return

            if response.status == "incomplete":
                if request_number == MAX_API_REQUESTS:
                    raise AgentLimitReached(
                        f"API request limit reached. Interaction ID: {response.id}"
                    )
                print("Token limit reached; continuing interaction...")
                request = {
                    "agent": AGENT_ID,
                    "previous_interaction_id": response.id,
                    "environment": response.environment_id or request["environment"],
                    "tools": tool_descriptions,
                    "input": "continue",
                }
                continue

            if response.status != "requires_action":
                raise RuntimeError(
                    f"Agent stopped with status {response.status}. "
                    f"Interaction ID: {response.id}"
                )
            if request_number == MAX_API_REQUESTS:
                raise AgentLimitReached("API request limit reached; tools not executed.")

            steps = response.steps or []
            answered_ids = {
                step.call_id for step in steps if step.type == "function_result"
            }
            pending_calls = [
                step for step in steps
                if step.type == "function_call" and step.id not in answered_ids
            ]
            if not pending_calls:
                raise RuntimeError("Agent supplied no pending MCP tool calls.")

            function_results = []
            for call in pending_calls:
                print("\nRequested tool:", call.name, flush=True)
                if call.id in saved_results:
                    result = saved_results[call.id]
                    print("Reusing saved result.")
                else:
                    try:
                        if call.name not in available_names:
                            raise PermissionError(f"Tool not allowed: {call.name}")

                        arguments = call.arguments or {}
                        if isinstance(arguments, str):
                            arguments = json.loads(arguments)
                        if not isinstance(arguments, dict):
                            raise ValueError("Tool arguments must be an object.")
                        if tool_call_count >= MAX_TOOL_CALLS:
                            raise AgentLimitReached("Local tool-call limit reached.")

                        tool_call_count += 1
                        mcp_result = await mcp_client.call_tool(call.name, arguments)
                        result = format_tool_result(unpack_mcp_result(mcp_result))
                        print("MCP tool execution returned.")

                    except AgentLimitReached:
                        raise
                    except Exception as error:
                        result = {"tool_failed": True, "error": str(error)}
                        print("Tool failed:", error)
                    saved_results[call.id] = result

                print("Result:", result.get("summary", result.get("error", "")))

                function_results.append({
                    "type": "function_result",
                    "name": call.name,
                    "call_id": call.id,
                    "result": result,
                })

            request = {
                "agent": AGENT_ID,
                "previous_interaction_id": response.id,
                "environment": response.environment_id or request["environment"],
                "tools": tool_descriptions,
                "input": function_results,
            }

    raise AgentLimitReached("API request limit reached before completion.")


async def main(list_only=False):
    script_dir = Path(__file__).resolve().parent
    server_file = script_dir / "vivado_tool_mcp.py"
    if not server_file.is_file():
        raise FileNotFoundError(f"MCP server script not found: {server_file}")

    server = StdioServerParameters(
        command=sys.executable,
        args=["-u", str(server_file)],
        cwd=str(script_dir),
        env=os.environ.copy(),
    )
    async with MCPClient(server, read_timeout_seconds=MCP_TIMEOUT_SECONDS) as mcp_client:
        listed_tools = await mcp_client.list_tools()
        print("Connected to the Vivado MCP server.")
        print("Discovered tools:")
        for tool in listed_tools.tools:
            allowed = tool.name in ALLOWED_MCP_TOOLS
            print(f" - {tool.name}: {'ALLOWED' if allowed else 'NOT EXPOSED'}")

        if list_only:
            print("\nConnection verified. No agent requests sent.")
            return

        tool_descriptions = [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            }
            for tool in listed_tools.tools if tool.name in ALLOWED_MCP_TOOLS
        ]
        if not tool_descriptions:
            raise RuntimeError("No allowed tools discovered. Check ALLOWED_MCP_TOOLS.")
        skill_file = script_dir / "skills" / "vivado-flow" / "SKILL.md"
        skill = skill_file.read_text(encoding="utf-8")
        user_request = input("Enter your FPGA task: ").strip()
        if not user_request:
            raise ValueError("FPGA task cannot be empty.")
        task = skill + "\n\nUser Request:\n" + user_request

        await run_agent(mcp_client, tool_descriptions, task)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list-tools", action="store_true",
        help="Check MCP discovery without using the agent API."
    )
    options = parser.parse_args()
    try:
        asyncio.run(main(list_only=options.list_tools))
    except KeyboardInterrupt:
        print("\nStopped by the user.", file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        print("Agent execution stopped:", error, file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
