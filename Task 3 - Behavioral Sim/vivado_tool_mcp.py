"""Expose local Vivado Python tools through MCP."""

import sys
from contextlib import redirect_stdout
from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

# Keep ordinary print statements away from MCP stdout.
with redirect_stdout(sys.stderr):
    import vivado_tools

mcp = MCPServer("Vivado Tools")


def call_local(function, *args, **kwargs):
    """Call a local function and return useful errors to the agent."""
    with redirect_stdout(sys.stderr):
        try:
            return function(*args, **kwargs)
        except Exception as error:
            raise ToolError(str(error)) from error


# 1. Create/open a Vivado project.
@mcp.tool()
def create_project() -> dict:
    """Run build_project.tcl and return exit code and log path.

    On failure, return at most the last 3000 characters of stdout/stderr.
    Use summarize_vivado_log for detailed diagnostics.
    """
    result = dict(call_local(vivado_tools.create_project))

    for field in ("stdout", "stderr"):
        if result["exit_code"] == 0:
            result.pop(field, None)
        elif isinstance(result.get(field), str) and len(result[field]) > 3000:
            result[field] = result[field][-3000:]
            result[field + "_truncated"] = True

    return result


# 2. Summarize Vivado log messages.
@mcp.tool()
def summarize_vivado_log(
    log_file: Annotated[str, Field(description="Path to the Vivado log file.")],
    filter: Annotated[
        Literal["errors", "warnings", "critical", "info", "all", "default"],
        Field(description="Message severity filter; default includes errors and warnings."),
    ] = "default",
) -> dict:
    """Return severity totals and message groups, without extra examples."""
    return call_local(
        vivado_tools.summarize_vivado_log,
        log_file=log_file,
        filter=filter,
        max_messages=0,
    )


# 3. Read the project Tcl script.
@mcp.tool()
def read_project_script() -> dict:
    """Return build_project.tcl path, contents and line count."""
    return call_local(vivado_tools.read_project_script)


# 4. Edit the project Tcl script.
@mcp.tool()
def edit_project_script(
    old_text: Annotated[
        str, Field(description="Exact old Tcl text identifying one location.")
    ],
    new_text: Annotated[
        str, Field(description="Replacement Tcl text; empty string deletes the match.")
    ],
) -> dict:
    """Replace exactly one matching Tcl snippet and back up the old file.

    Use only for project setup repairs, preserving intended device/design inputs.
    """
    return call_local(vivado_tools.edit_project_script, old_text, new_text)


# 5. Generate Verilog with Gemini.
@mcp.tool()
def generate_verilog(
    requirement: Annotated[
        str, Field(description="Natural-language requirement for synthesizable Verilog-2001 RTL.")
    ],
    file_path: Annotated[
        str, Field(description="Destination .v file path; existing content will be overwritten.")
    ],
) -> str:
    """Ask Gemini to generate Verilog and save it to file_path.

    This overwrites an existing file. Returns the saved file path.
    """
    return call_local(vivado_tools.generate_verilog, requirement, file_path)


# 6. Replace a Verilog snippet without calling any LLM API.
@mcp.tool()
def update_verilog(
    file_path: Annotated[
        str, Field(description="Path of the existing Verilog file to modify.")
    ],
    old_text: Annotated[
        str, Field(description="Exact text to replace; must occur exactly once.")
    ],
    new_text: Annotated[
        str, Field(description="Replacement Verilog text. Empty string deletes the match.")
    ],
) -> str:
    """Replace one unique snippet in a Verilog file, returning the file path.

    Does not call Gemini or another LLM; the agent supplies both snippets.
    """
    return call_local(vivado_tools.update_verilog, file_path, old_text, new_text)


# 7. Refresh the Vivado filesets and compile order.
@mcp.tool()
def refresh_filesets() -> dict:
    """Add new RTL/TB/XDC files, remove missing references, and update compile order.

    Runs refresh_fileset.tcl before performing Behavioral Simulation, Synthesis, Implementation
    Returns the exit code, log path,
    and summary of added/removed files.
    """
    result = dict(call_local(vivado_tools.refresh_filesets))

    # Return only the summary on success; keep limited diagnostics on failure.
    for field in ("stdout", "stderr"):
        if result["exit_code"] == 0 and result["summary"]:
            result.pop(field, None)
        elif isinstance(result.get(field), str) and len(result[field]) > 3000:
            result[field] = result[field][-3000:]
            result[field + "_truncated"] = True

    return result


# 8. Run Vivado behavioral simulation and parse the testbench summary.
@mcp.tool()
def run_behavioral_simulation(
    timeout_seconds: Annotated[
        int, Field(description="Maximum wall-clock execution time in seconds.", ge=1)
    ] = 120,
) -> dict:
    """Run behav_sim.tcl and return tests passed, failed, and coverage."""
    return call_local(vivado_tools.run_behavioral_simulation, timeout_seconds)


if __name__ == "__main__":
    mcp.run(transport="stdio")
