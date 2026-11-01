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
        except ToolError:
            raise
        except Exception as error:
            raise ToolError(str(error)) from error


def tool_response(message: str, data=None, status: str = "SUCCESS") -> dict:
    """Return the same response structure for every MCP tool."""
    return {
        "status": status,
        "message": message,
        "data": {} if data is None else data,
    }


# 1. Create/open a Vivado project.
@mcp.tool()
def create_project() -> dict:
    """Run build_project.tcl and report its status and log path."""
    result = dict(call_local(vivado_tools.create_project))

    # Keep detailed diagnostics only for a failed command.
    for field in ("stdout", "stderr"):
        if result["exit_code"] == 0:
            result.pop(field, None)
        elif isinstance(result.get(field), str) and len(result[field]) > 3000:
            result[field] = result[field][-3000:]
            result[field + "_truncated"] = True

    if result["exit_code"] != 0:
        return tool_response("Project creation failed", result, "FAILED")

    return tool_response("Project created successfully", result)


# 2. Summarize Vivado log messages.
@mcp.tool()
def summarize_vivado_log(
    log_file: Annotated[
        str, Field(description="Path to the Vivado log file.")
    ],
    filter: Annotated[
        Literal["errors", "warnings", "critical", "info", "all", "default"],
        Field(description="Message severity filter; default includes errors and warnings."),
    ] = "default",
) -> dict:
    """Return severity totals and message groups, without extra examples."""
    result = call_local(
        vivado_tools.summarize_build_log,
        log_file=log_file,
        filter=filter,
        max_messages=0,
    )
    return tool_response("Vivado log summarized", result)


# 3. Read the project Tcl script.
@mcp.tool()
def read_project_script() -> dict:
    """Read build_project.tcl and return its content and line count."""
    result = call_local(vivado_tools.read_project_script)
    return tool_response("Project Tcl script read", result)


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
    """Replace one matching Tcl snippet and back up the old file."""
    result = dict(call_local(vivado_tools.edit_project_script, old_text, new_text))

    # The agent already supplied this text; no need to send it back.
    result.pop("old_text", None)
    result.pop("new_text", None)

    return tool_response("Project Tcl script updated", result)


# 5. Generate Verilog with Gemini.
@mcp.tool()
def generate_verilog(
    requirement: Annotated[
        str, Field(description="Natural-language requirement for synthesizable Verilog-2001 RTL.")
    ],
    file_path: Annotated[
        str, Field(description="Destination .v file path; existing content will be overwritten.")
    ],
) -> dict:
    """Generate Verilog and report the saved file path."""
    saved_path = call_local(vivado_tools.generate_verilog, requirement, file_path)
    return tool_response("Verilog file generated", {"file_path": saved_path})


# 6. Update the fixed AXI4-Lite RTL file.
@mcp.tool()
def rtl_update(
    old_text: Annotated[str, Field(description="Exact existing Verilog code to replace")],
    new_text: Annotated[str, Field(description="Replacement Verilog code")],
) -> dict:
    """Update rtl/axil_mem.v; do not provide a filename or file path."""
    result = call_local(vivado_tools.rtl_update, old_text, new_text)

    if result != "SUCCESS":
        raise ToolError(f"RTL update did not report success: {result}")

    return tool_response("RTL updated")


# 7. Refresh the Vivado filesets and compile order.
@mcp.tool()
def refresh_filesets() -> dict:
    """Refresh project sources and return the status, log, and summary."""
    result = dict(call_local(vivado_tools.refresh_filesets))

    for field in ("stdout", "stderr"):
        if result["exit_code"] == 0 and result.get("summary"):
            result.pop(field, None)
        elif isinstance(result.get(field), str) and len(result[field]) > 3000:
            result[field] = result[field][-3000:]
            result[field + "_truncated"] = True

    if result["exit_code"] != 0:
        return tool_response("Fileset refresh failed", result, "FAILED")

    return tool_response("Filesets refreshed", result)


# 8. Run behavioral simulation and filter its log.
@mcp.tool()
def run_behavioral_simulation(
    timeout_seconds: Annotated[
        int, Field(description="Maximum wall-clock execution time in seconds.", ge=1)
    ] = 120,
) -> dict:
    """Run behavioral simulation and return the filtered log path.

    A returned log does not mean all tests passed. Use read_vivado_log
    to inspect TESTS_PASSED, TESTS_FAILED, COVERAGE, and RESULT.
    """
    log_file = call_local(vivado_tools.run_behavioral_simulation, timeout_seconds)
    return tool_response("Simulation log generated; check test results", {"log_file": log_file})


# 9. Read a Vivado log by workflow step.
@mcp.tool()
def read_vivado_log(
    step: Annotated[
        Literal["create_project", "behavioral_simulation"],
        Field(description="Vivado workflow step whose log should be read."),
    ],
) -> dict:
    """Read a project-creation or filtered behavioral-simulation log."""
    content = call_local(vivado_tools.read_vivado_log, step)
    return tool_response("Vivado log read", {"content": content})


# 10. Read the specified Verilog RTL source.
@mcp.tool()
def read_verilog(
    file_name: Annotated[
        str,
        Field(description="Name of Verilog RTL file to read, e.g., axil_mem.v. Provide filename only, without directory path."),
    ],
) -> dict:
    """Find and read the specified Verilog RTL file."""
    code = call_local(vivado_tools.read_verilog, file_name)
    return tool_response("Verilog RTL file read", {"content": code})

@mcp.tool()
def check_constraints() -> dict:
    """Elaborate RTL and check PACKAGE_PIN and IOSTANDARD constraints."""

    result = call_local(vivado_tools.check_constraints)

    return tool_response("Constraint verification completed", result)
    
    
    
@mcp.tool()
def run_synthesis() -> dict:
    """Run Vivado synthesis and return diagnostic counts and filtered log path."""

    result = call_local(vivado_tools.run_synthesis)

    return tool_response("Synthesis execution completed", result)

@mcp.tool()
def read_synthesis_diagnostics() -> dict:
    """Read synthesis warnings and errors for analysis."""

    result = call_local(
        vivado_tools.read_synthesis_diagnostics
    )

    return tool_response(
        "Synthesis diagnostics retrieved",
        result
    )
    
    
    
@mcp.tool()
def check_device_part() -> dict:
    """Verify the FPGA part and update it to xc7z010clg400-1 if needed."""

    result = call_local(vivado_tools.check_device_part)

    message = (
        "Device part verification completed"
        if result["exit_code"] == 0
        else "Device part verification failed"
    )

    return tool_response(message, result)    

@mcp.tool()
def read_synthesis_diagnostics() -> dict:
    """Read synthesis warnings and errors for analysis before implementation."""

    result = call_local(
        vivado_tools.read_synthesis_diagnostics
    )

    return tool_response(
        "Synthesis diagnostics retrieved",
        {"content": result}
    )


@mcp.tool()
def run_implementation() -> dict:
    """Run FPGA implementation and return diagnostic summary."""

    result = call_local(
        vivado_tools.run_implementation
    )

    return tool_response(
        "Implementation execution completed",
        result
    )


@mcp.tool()
def read_implementation_diagnostics() -> dict:
    """Read implementation warnings and errors for analysis."""

    result = call_local(
        vivado_tools.read_implementation_diagnostics
    )

    return tool_response(
        "Implementation diagnostics retrieved",
        result
    )

@mcp.tool()
def generate_bitstream() -> dict:
    """Generate FPGA bitstream from the successfully implemented design."""

    result = call_local(
        vivado_tools.generate_bitstream
    )

    message = (
        "Bitstream generation completed"
        if result["exit_code"] == 0
        else "Bitstream generation failed"
    )

    return tool_response(message, result)


    
if __name__ == "__main__":
    mcp.run(transport="stdio")
