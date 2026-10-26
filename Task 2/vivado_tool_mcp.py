"""Expose the existing vivado_tools.py functions through local MCP."""

import sys
from contextlib import redirect_stdout
from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

# stdout carries MCP messages. Send ordinary Python prints to stderr.
with redirect_stdout(sys.stderr):
    import vivado_tools


mcp = MCPServer("Vivado Tools")


def call_local(function, *args, **kwargs):
    """Keep prints off MCP stdout and preserve useful local error messages."""
    with redirect_stdout(sys.stderr):
        try:
            return function(*args, **kwargs)
        except Exception as error:
            raise ToolError(str(error)) from error

#decorator registers the Python function as an MCP tool
@mcp.tool()
def create_project() -> dict:
    """Create or open the local Vivado project using build_project.tcl.
    Returns the exit code and log path. On failure, also returns truncated
    stdout and stderr. 
    Use summarize_vivado_log to inspect warnings.
    """
    
    result = dict(call_local(vivado_tools.create_project))

    # Reduce the amount of output sent through MCP and back to the agent.
    for field in ("stdout", "stderr"):
        if result["exit_code"] == 0:
            result.pop(field, None)
        elif isinstance(result.get(field), str):
            if len(result[field]) > 3000:
                result[field] = result[field][-3000:]
                result[field + "_truncated"] = True

    return result
    
#     return {
#    "exit_code": result.returncode,
#    "log_file": str(log_file),
#    "stdout": result.stdout,
#    "stderr": result.stderr,
#}
# Process stdout and stderr independently to reduce MCP response size.
#
# Case 1: exit_code == 0 (Success)
#   - Remove both stdout and stderr from the result.
#   - Return only exit_code and log_file.
#   Example:
#     {"exit_code": 0, "log_file": "logs/vivado.log"}
#
# Case 2: exit_code != 0 (Failure, output <= 3000 characters)
#   - Preserve the complete stdout and stderr.
#   Example:
#     {
#         "exit_code": 1,
#         "log_file": "logs/vivado.log",
#         "stdout": "Starting Vivado...",
#         "stderr": "ERROR: Invalid FPGA part specified."
#     }
#
# Case 3: exit_code != 0 (Failure, output > 3000 characters)
#   - Keep only the last 3000 characters of each oversized output.
#   - Add stdout_truncated=True and/or stderr_truncated=True.
#   - Each output field is checked independently.
#   Example:
#     {
#         "exit_code": 1,
#         "log_file": "logs/vivado.log",
#         "stdout": "...last 3000 characters...",
#         "stdout_truncated": True,
#         "stderr": "...last 3000 characters...",
#         "stderr_truncated": True
#     }
#
# Note: This optimization reduces unnecessary token consumption
# when returning Vivado execution results to the LLM agent.


# str: Specifies that log_file must be a string.
# Annotated: Attaches additional metadata to the type.
# Field(description=...): Describes the argument in the MCP tool schema.
# Literal: Restricts the argument to predefined values.
# ge=0: Ensures an integer value is greater than or equal to zero.

@mcp.tool()
def summarize_vivado_log(
    log_file: Annotated[
        str,
        Field(description="Path to the Vivado log file.")
    ],
    filter: Annotated[
        Literal[
            "errors", "warnings", "critical",
            "info", "all", "default"
        ],
        Field(
            description=(
                "Filter Vivado log messages by severity. "
                "'errors' includes errors only; "
                "'warnings' includes warnings only; "
                "'critical' includes critical warnings only; "
                "'info' includes informational messages; "
                "'all' includes all severities; "
                "'default' includes errors, critical warnings, and warnings."
            )
        )
    ] = "default",
) -> dict:
    """
    Return severity totals and messages grouped by severity and ID.

    Each group includes a count, summary, and one complete
    representative example.

    The default filter includes errors, critical warnings,
    and warnings.

    Additional examples are disabled to reduce LLM token usage.
    """
    return call_local(
        vivado_tools.summarize_vivado_log,
        log_file=log_file,
        filter=filter,
        max_messages=0,
    )


@mcp.tool()
def read_project_script() -> dict:
    """Read build_project.tcl.

    Returns the script path, complete contents, and line count.
    """
    return call_local(vivado_tools.read_project_script)


@mcp.tool()
def edit_project_script(
    old_text: Annotated[
        str,
        Field(description="Exact existing text identifying one location."),
    ],
    new_text: Annotated[
        str,
        Field(description="Replacement Tcl text. Empty deletes the match."),
    ],
) -> dict:
    """Replace one exact occurrence of old_text in build_project.tcl.

    Creates a backup first. Rejects missing or ambiguous matches.
    Permitted only for project-setup corrections. Preserve the intended
    target device and design files.
    """
    return call_local(vivado_tools.edit_project_script, old_text, new_text)


if __name__ == "__main__":
    mcp.run(transport="stdio")
