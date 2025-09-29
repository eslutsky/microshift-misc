#!/usr/bin/env python3
"""
Working MCP Server for MicroShift VM Management
Compatible with current MCP library version
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel.server import NotificationOptions
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the parent directory where run.sh is located
SCRIPT_DIR = Path(__file__).parent.parent.absolute()  # Parent of mcp-server/
RUN_SCRIPT = SCRIPT_DIR / "run.sh"

class MicroShiftMCPServer:
    def __init__(self):
        self.server = Server("microshift-vm-manager")
        self.setup_handlers()
    
    def setup_handlers(self):
        @self.server.list_tools()
        async def handle_list_tools() -> ListToolsResult:
            """List all available tools."""
            return ListToolsResult(
                tools=[
                    Tool(
                        name="create_vm",
                        description="Create EC2 VM instance for MicroShift testing",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "env": {
                                    "type": "string",
                                    "enum": ["upstream", "ci", "ci-pr"],
                                    "default": "upstream",
                                    "description": "Environment type (upstream, ci, ci-pr)"
                                },
                                "region": {
                                    "type": "string",
                                    "default": "eu-west-1",
                                    "description": "AWS region for VM creation"
                                },
                                "instance_type": {
                                    "type": "string",
                                    "default": "m4.4xlarge",
                                    "description": "EC2 instance type"
                                },
                                "stack_name": {
                                    "type": "string",
                                    "description": "Custom stack name (optional)"
                                }
                            },
                            "required": []
                        }
                    ),
                    Tool(
                        name="provision_vm",
                        description="Provision and configure VM with MicroShift",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "config": {
                                    "type": "string",
                                    "enum": ["ci", "ci-pr", "upstream"],
                                    "default": "upstream",
                                    "description": "Configuration type (ci, ci-pr, upstream)"
                                },
                                "pr_number": {
                                    "type": "string",
                                    "description": "PR number for ci-pr configuration"
                                },
                                "stack_name": {
                                    "type": "string",
                                    "description": "Filter by stack name (optional)"
                                }
                            },
                            "required": ["config"]
                        }
                    ),
                    Tool(
                        name="stop_vm",
                        description="Stop running EC2 VM instances",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "stack_name": {
                                    "type": "string",
                                    "description": "Filter by stack name (optional)"
                                }
                            },
                            "required": []
                        }
                    ),
                    Tool(
                        name="start_vm",
                        description="Start stopped EC2 VM instances",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "stack_name": {
                                    "type": "string",
                                    "description": "Filter by stack name (optional)"
                                }
                            },
                            "required": []
                        }
                    ),
                    Tool(
                        name="get_vm_status",
                        description="Get current VM status and kubectl environment",
                        inputSchema={
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    )
                ]
            )

        @self.server.call_tool()
        async def handle_call_tool(request: CallToolRequest) -> CallToolResult:
            """Handle tool calls."""
            try:
                if request.name == "create_vm":
                    return await self._create_vm(request.arguments or {})
                elif request.name == "provision_vm":
                    return await self._provision_vm(request.arguments or {})
                elif request.name == "stop_vm":
                    return await self._stop_vm(request.arguments or {})
                elif request.name == "start_vm":
                    return await self._start_vm(request.arguments or {})
                elif request.name == "get_vm_status":
                    return await self._get_vm_status(request.arguments or {})
                else:
                    raise ValueError(f"Unknown tool: {request.name}")
            except Exception as e:
                logger.error(f"Error in {request.name}: {str(e)}")
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Error: {str(e)}")],
                    isError=True
                )

    async def _run_script(self, args: List[str], env_vars: Optional[Dict[str, str]] = None) -> CallToolResult:
        """Run the run.sh script with given arguments."""
        if not RUN_SCRIPT.exists():
            raise FileNotFoundError(f"run.sh script not found at {RUN_SCRIPT}")
        
        cmd = [str(RUN_SCRIPT)] + args
        logger.info(f"Running command: {' '.join(cmd)}")
        
        # Set up environment
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                cwd=SCRIPT_DIR
            )
            
            stdout, _ = await process.communicate()
            output = stdout.decode('utf-8')
            
            if process.returncode == 0:
                return CallToolResult(
                    content=[TextContent(
                        type="text", 
                        text=f"✅ Command completed successfully:\n\n{output}"
                    )]
                )
            else:
                return CallToolResult(
                    content=[TextContent(
                        type="text", 
                        text=f"❌ Command failed with return code {process.returncode}:\n\n{output}"
                    )],
                    isError=True
                )
        except Exception as e:
            raise Exception(f"Failed to execute command: {str(e)}")

    async def _create_vm(self, args: Dict[str, Any]) -> CallToolResult:
        """Create VM instance."""
        cmd_args = []
        env_vars = {}
        
        # Add stack name filter if provided
        if args.get("stack_name"):
            cmd_args.extend(["-s", args["stack_name"]])
        
        # Set mode and environment
        env_type = args.get("env", "upstream")
        cmd_args.extend(["create", env_type])
        
        # Set environment variables for customization
        if args.get("region"):
            env_vars["AWS_REGION"] = args["region"]
        if args.get("instance_type"):
            env_vars["INSTANCE_TYPE"] = args["instance_type"]
        
        return await self._run_script(cmd_args, env_vars)

    async def _provision_vm(self, args: Dict[str, Any]) -> CallToolResult:
        """Provision VM with MicroShift configuration."""
        cmd_args = []
        env_vars = {}
        
        # Add stack name filter if provided
        if args.get("stack_name"):
            cmd_args.extend(["-s", args["stack_name"]])
        
        # Set mode and configuration
        config = args.get("config", "upstream")
        cmd_args.extend(["provision", config])
        
        # Set environment variables for ci-pr configuration
        if config == "ci-pr":
            if args.get("pr_number"):
                env_vars["PR_NUMBER"] = args["pr_number"]
        
        return await self._run_script(cmd_args, env_vars)

    async def _stop_vm(self, args: Dict[str, Any]) -> CallToolResult:
        """Stop VM instances."""
        cmd_args = []
        
        if args.get("stack_name"):
            cmd_args.extend(["-s", args["stack_name"]])
        
        cmd_args.append("stop")
        return await self._run_script(cmd_args)

    async def _start_vm(self, args: Dict[str, Any]) -> CallToolResult:
        """Start VM instances."""
        cmd_args = []
        
        if args.get("stack_name"):
            cmd_args.extend(["-s", args["stack_name"]])
        
        cmd_args.append("start")
        return await self._run_script(cmd_args)

    async def _get_vm_status(self, args: Dict[str, Any]) -> CallToolResult:
        """Get VM status and kubectl environment."""
        cmd_args = ["env"]
        return await self._run_script(cmd_args)

    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="microshift-vm-manager",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

def main():
    """Main entry point."""
    server = MicroShiftMCPServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()

