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
        print(
            "Agent execution stopped:",
            error,
            file=sys.stderr,
        )
        sys.exit(1)