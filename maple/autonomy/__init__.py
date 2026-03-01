"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can redistribute it and/or
modify it under the terms of the GNU Affero General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU Affero General Public License for more details. You should have
received a copy of the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""

"""MAPLE Autonomy Layer - Autonomous agentic AI capabilities."""

from .tools import Tool, ToolRegistry
from .memory import WorkingMemory, EpisodicMemory, SemanticMemory, MemoryManager
from .agent import AutonomousAgent, AutonomousConfig, Goal, ReasoningStep
from .orchestrator import AgentOrchestrator, TeamMember
from .observability import DecisionTrace, DecisionLogger, AgentSnapshot
from .mcp_tools import discover_mcp_tools, register_mcp_tools

__all__ = [
    'Tool', 'ToolRegistry',
    'WorkingMemory', 'EpisodicMemory', 'SemanticMemory', 'MemoryManager',
    'AutonomousAgent', 'AutonomousConfig', 'Goal', 'ReasoningStep',
    'AgentOrchestrator', 'TeamMember',
    'DecisionTrace', 'DecisionLogger', 'AgentSnapshot',
    'discover_mcp_tools', 'register_mcp_tools',
]
