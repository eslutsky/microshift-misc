#!/usr/bin/env python3
"""
MCP Server for MicroShift VM Management
Exposes actions from run.sh script via MCP protocol
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
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
    ImageContent,
    EmbeddedResource,
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
                                    "enum": ["upstream", "ci"],
                                    "default": "upstream",
                                    "description": "Environment type (upstream, ci)"
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
                                "ami_id": {
                                    "type": "string",
                                    "description": "AMI ID to use (optional, uses defaults if not provided)"
                                },
                                "stack_name": {
                                    "type": "string",
                                    "description": "Custom stack name (optional)"
                                },
                                "inventory_file": {
                                    "type": "string",
                                    "description": "Custom inventory file path (optional)"
                                },
                                "extra_args": {
                                    "type": "string",
                                    "description": "Additional ansible-playbook arguments"
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
                                "release_ver": {
                                    "type": "string",
                                    "description": "Release version for ci-pr configuration"
                                },
                                "stack_name": {
                                    "type": "string",
                                    "description": "Filter by stack name (optional)"
                                },
                                "inventory_file": {
                                    "type": "string",
                                    "description": "Custom inventory file path (optional)"
                                },
                                "extra_args": {
                                    "type": "string",
                                    "description": "Additional ansible-playbook arguments"
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
                                },
                                "inventory_file": {
                                    "type": "string",
                                    "description": "Custom inventory file path (optional)"
                                },
                                "extra_args": {
                                    "type": "string",
                                    "description": "Additional ansible-playbook arguments"
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
                                },
                                "inventory_file": {
                                    "type": "string",
                                    "description": "Custom inventory file path (optional)"
                                },
                                "extra_args": {
                                    "type": "string",
                                    "description": "Additional ansible-playbook arguments"
                                }
                            },
                            "required": []
                        }
                    ),
                    Tool(
                        name="destroy_vm",
                        description="Destroy EC2 VM instances",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "stack_name": {
                                    "type": "string",
                                    "description": "Filter by stack name (optional)"
                                },
                                "inventory_file": {
                                    "type": "string",
                                    "description": "Custom inventory file path (optional)"
                                },
                                "extra_args": {
                                    "type": "string",
                                    "description": "Additional ansible-playbook arguments"
                                }
                            },
                            "required": []
                        }
                    ),
                    Tool(
                        name="cleanup_old_vms",
                        description="Cleanup old EC2 VM instances",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "stack_name": {
                                    "type": "string",
                                    "description": "Filter by stack name (optional)"
                                },
                                "inventory_file": {
                                    "type": "string",
                                    "description": "Custom inventory file path (optional)"
                                },
                                "extra_args": {
                                    "type": "string",
                                    "description": "Additional ansible-playbook arguments"
                                }
                            },
                            "required": []
                        }
                    ),
                    Tool(
                        name="get_kube_env",
                        description="Set up kubectl environment and show pod status",
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
                elif request.name == "destroy_vm":
                    return await self._destroy_vm(request.arguments or {})
                elif request.name == "cleanup_old_vms":
                    return await self._cleanup_old_vms(request.arguments or {})
                elif request.name == "get_kube_env":
                    return await self._get_kube_env(request.arguments or {})
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
                        text=f"Command completed successfully:\n\n{output}"
                    )]
                )
            else:
                return CallToolResult(
                    content=[TextContent(
                        type="text", 
                        text=f"Command failed with return code {process.returncode}:\n\n{output}"
                    )],
                    isError=True
                )
        except Exception as e:
            raise Exception(f"Failed to execute command: {str(e)}")

    async def _create_vm(self, args: Dict[str, Any]) -> CallToolResult:
        """Create VM instance."""
        cmd_args = []
        env_vars = {}
        
        # Add inventory file option if provided
        if args.get("inventory_file"):
            cmd_args.extend(["-i", args["inventory_file"]])
        
        # Add stack name filter if provided
        if args.get("stack_name"):
            cmd_args.extend(["-s", args["stack_name"]])
        
        # Set mode and environment
        env_type = args.get("env", "upstream")
        cmd_args.extend(["create", env_type])
        
        # Add extra arguments if provided
        if args.get("extra_args"):
            cmd_args.extend(args["extra_args"].split())
        
        # Set environment variables for customization
        if args.get("region"):
            env_vars["AWS_REGION"] = args["region"]
        if args.get("instance_type"):
            env_vars["INSTANCE_TYPE"] = args["instance_type"]
        if args.get("ami_id"):
            env_vars["AMI_ID"] = args["ami_id"]
        
        return await self._run_script(cmd_args, env_vars)

    async def _provision_vm(self, args: Dict[str, Any]) -> CallToolResult:
        """Provision VM with MicroShift configuration."""
        cmd_args = []
        env_vars = {}
        
        # Add inventory file option if provided
        if args.get("inventory_file"):
            cmd_args.extend(["-i", args["inventory_file"]])
        
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
            if args.get("release_ver"):
                env_vars["RELEASE_VER"] = args["release_ver"]
        
        # Add extra arguments if provided
        if args.get("extra_args"):
            cmd_args.extend(args["extra_args"].split())
        
        return await self._run_script(cmd_args, env_vars)

    async def _stop_vm(self, args: Dict[str, Any]) -> CallToolResult:
        """Stop VM instances."""
        cmd_args = []
        
        # Add inventory file option if provided
        if args.get("inventory_file"):
            cmd_args.extend(["-i", args["inventory_file"]])
        
        # Add stack name filter if provided
        if args.get("stack_name"):
            cmd_args.extend(["-s", args["stack_name"]])
        
        cmd_args.append("stop")
        
        # Add extra arguments if provided
        if args.get("extra_args"):
            cmd_args.extend(args["extra_args"].split())
        
        return await self._run_script(cmd_args)

    async def _start_vm(self, args: Dict[str, Any]) -> CallToolResult:
        """Start VM instances."""
        cmd_args = []
        
        # Add inventory file option if provided
        if args.get("inventory_file"):
            cmd_args.extend(["-i", args["inventory_file"]])
        
        # Add stack name filter if provided
        if args.get("stack_name"):
            cmd_args.extend(["-s", args["stack_name"]])
        
        cmd_args.append("start")
        
        # Add extra arguments if provided
        if args.get("extra_args"):
            cmd_args.extend(args["extra_args"].split())
        
        return await self._run_script(cmd_args)

    async def _destroy_vm(self, args: Dict[str, Any]) -> CallToolResult:
        """Destroy VM instances."""
        cmd_args = []
        
        # Add inventory file option if provided
        if args.get("inventory_file"):
            cmd_args.extend(["-i", args["inventory_file"]])
        
        # Add stack name filter if provided
        if args.get("stack_name"):
            cmd_args.extend(["-s", args["stack_name"]])
        
        cmd_args.append("destroy")
        
        # Add extra arguments if provided
        if args.get("extra_args"):
            cmd_args.extend(args["extra_args"].split())
        
        return await self._run_script(cmd_args)

    async def _cleanup_old_vms(self, args: Dict[str, Any]) -> CallToolResult:
        """Cleanup old VM instances."""
        cmd_args = []
        
        # Add inventory file option if provided
        if args.get("inventory_file"):
            cmd_args.extend(["-i", args["inventory_file"]])
        
        # Add stack name filter if provided
        if args.get("stack_name"):
            cmd_args.extend(["-s", args["stack_name"]])
        
        cmd_args.append("cleanup")
        
        # Add extra arguments if provided
        if args.get("extra_args"):
            cmd_args.extend(args["extra_args"].split())
        
        return await self._run_script(cmd_args)

    async def _get_kube_env(self, args: Dict[str, Any]) -> CallToolResult:
        """Get Kubernetes environment status."""
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
