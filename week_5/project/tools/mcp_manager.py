import os
import re
import json
import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

def load_mcp_config(path: str = "config.json") -> dict:
    """Reads config.json and substitutes ${ENV_VAR} references from the environment."""
    if not os.path.exists(path):
        return {}
    
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    def substitute(match):
        var = match.group(1)
        value = os.environ.get(var)
        if value is None:
            print(f"\033[93m[Warning] config.json references ${{{var}}}, but it is not set in .env. Skipping auth header.\033[0m")
            return ""
        return value

    resolved = re.sub(r"\$\{([A-Z0-9_]+)\}", substitute, raw)
    try:
        data = json.loads(resolved)
        return data.get("mcpServers", {})
    except json.JSONDecodeError as e:
        print(f"\033[91m[Error] Malformed config.json after env substitution: {e}\033[0m")
        return {}

class MCPManager:
    """Connects to configured servers and exposes their tools as a unified list."""
    def __init__(self):
        self.stack = AsyncExitStack()
        self.openai_tools = []
        self.tool_to_session = {}
        self.active_servers = []

    async def connect_all(self, config_path: str = "config.json"):
        servers = load_mcp_config(config_path)
        for name, cfg in servers.items():
            await self.connect_server(name, cfg)

    async def connect_server(self, name: str, cfg: dict):
        url = cfg.get("url")
        if not url:
            return
        
        headers = {k: v for k, v in cfg.get("headers", {}).items() if v}
        try:
            read, write, _ = await self.stack.enter_async_context(
                streamablehttp_client(url, headers=headers if headers else None)
            )
            session = await self.stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools = await session.list_tools()
            count = 0
            for tool in tools.tools:
                prefixed_name = f"{name}_{tool.name}"
                self.tool_to_session[prefixed_name] = session
                self.openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": prefixed_name,
                        "description": f"[{name.upper()} MCP] {tool.description}",
                        "parameters": tool.inputSchema,
                    },
                })
                count += 1
            
            if name not in self.active_servers:
                self.active_servers.append(name)
            print(f"\033[92m[MCP] Connected server '{name}': Loaded {count} remote tools.\033[0m")
        except Exception as e:
            print(f"\033[91m[MCP Error] Failed to connect to '{name}' ({url}): {e}\033[0m")

    async def call_tool(self, prefixed_name: str, args: dict) -> str:
        if prefixed_name not in self.tool_to_session:
            return f"Error: MCP tool '{prefixed_name}' is not routed to an active session."
        
        session = self.tool_to_session[prefixed_name]
        original_name = prefixed_name.split("_", 1)[1] if "_" in prefixed_name else prefixed_name
        try:
            result = await session.call_tool(original_name, args)
            if result and hasattr(result, 'content') and result.content:
                return "".join([block.text for block in result.content if hasattr(block, 'text')])
            return "MCP server returned an empty payload."
        except Exception as e:
            return f"Remote MCP Execution Error: {str(e)}"

    async def aclose(self):
        try:
            await self.stack.aclose()
        except (RuntimeError, GeneratorExit, Exception):
            pass
        finally:
            self.openai_tools.clear()
            self.tool_to_session.clear()
            self.active_servers.clear()