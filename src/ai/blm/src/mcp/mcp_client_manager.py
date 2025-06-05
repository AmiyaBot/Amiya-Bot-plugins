import os
import json
import traceback
from typing import Dict, List, Optional, Tuple, Any
from contextlib import AsyncExitStack

from amiyabot.log import LoggerManager

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.sse import sse_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

logger = LoggerManager('MCPClientManager')

class MCPClientManager:
    def __init__(self,plugin):
        self.plugin = plugin

        if not MCP_AVAILABLE:
            logger.warning("MCP library not found. MCPClientManager will be disabled.")
            self.disabled = True
            return
        else:
            self.disabled = False

        self.exit_stack = AsyncExitStack()
        self.active_sessions: Dict[str, ClientSession] = {}
        self.all_server_tools: Dict[str, List] = {}
        self._load_config()

    def _load_config(self):
        mcp_config = self.plugin.get_config("MCP")
        if not mcp_config and mcp_config.get("enable", False):
            logger.warning("MCP configuration not found or disabled. ")
            self.config = {"mcpServers": {}}
            return
        
        config = mcp_config.get("config", {})
        if not config:
            logger.warning("MCP configuration is empty. ")
            self.config = {"mcpServers": {}}
            return

        config = json.loads(config) if isinstance(config, str) else config

        self.config = config

    async def initialize(self):
        if self.disabled:
            return
        await self.connect_to_all_servers()

    async def connect_to_all_servers(self):
        if self.disabled:
            return
        for name, conf in self.config.get("mcpServers", {}).items():
            if conf.get("disabled", False):
                continue

            try:
                if conf.get("transportType") == "sse":
                    session = await self._connect_sse(name, conf)
                else:
                    session = await self._connect_stdio(name, conf)

                if session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    self.active_sessions[name] = session
                    self.all_server_tools[name] = tools
                    logger.info(f"Connected to MCP server '{name}' with {len(tools)} tools.")

            except Exception as e:
                logger.error(f"Error connecting to server {name}: {e}")

    async def _connect_stdio(self, name, conf):
        params = StdioServerParameters(
            command=conf.get("command", "python"),
            args=conf.get("args", []),
            env=conf.get("env", None)
        )
        client = await self.exit_stack.enter_async_context(stdio_client(params))
        return await self.exit_stack.enter_async_context(ClientSession(*client))

    async def _connect_sse(self, name, conf):
        url = conf.get("url")
        if not url:
            logger.warning(f"SSE server '{name}' missing URL.")
            return None
        client = await self.exit_stack.enter_async_context(sse_client(url=url))
        return await self.exit_stack.enter_async_context(ClientSession(*client))

    def get_tool_list(self) -> List[Dict[str, Any]]:
        if self.disabled:
            return []
        tools = []
        for server, tool_list in self.all_server_tools.items():
            for tool in tool_list:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": f"{server}:{tool.name}",
                        "description": f"[{server}] {tool.description}",
                        "parameters": tool.inputSchema
                    }
                })
        return tools

    async def execute_tool_call(self, tool_call, messages: List[Dict]) -> str:
        if self.disabled:
            return "[MCP功能未启用]"
        try:
            tool_call_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            if ":" in tool_call_name:
                server, tool = tool_call_name.split(":", 1)
            else:
                server = next(iter(self.active_sessions))
                tool = tool_call_name

            session = self.active_sessions.get(server)
            if not session:
                raise Exception(f"No active session for server '{server}'.")

            result = await session.call_tool(tool, args)
            messages.append({
                "role": "assistant",
                "tool_calls": [ {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call_name,
                        "arguments": json.dumps(args)
                    }
                }]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result.content)
            })
            return str(result.content)
        except Exception as e:
            logger.error(f"Tool call error: {e}")
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": f"[MCP工具调用失败: {e}]"
            })
            return f"[MCP工具调用失败: {e}]"

    async def cleanup(self):
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            logger.error(f"Failed to clean up MCPClientManager: {e}")
