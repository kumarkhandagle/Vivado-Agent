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

MAX_API_REQUESTS = 12
MAX_TOOL_CALLS = 12
MAX_EDIT_ATTEMPTS = 3
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
    """Print usage reported by Google for this interaction response."""
    usage = getattr(response, "usage", None)

    if usage is None:
        print("Token usage: not available in this response.")
        return

    print("Token usage (reported by Google):")

    fields = [
        ("Input tokens", "total_input_tokens"),
        ("Output tokens", "total_output_tokens"),
        ("Thinking tokens", "total_thought_tokens"),
        ("Cached tokens", "total_cached_tokens"),
        ("Tool-use tokens", "total_tool_use_tokens"),
        ("Total tokens", "total_tokens"),
    ]

    for label, field_name in fields:
        number = getattr(usage, field_name, None)
        if number is not None:
            print(f"  {label}: {number:,}")

    # The API determines the total. Do not add these categories manually,
    # because some token counts may overlap.
