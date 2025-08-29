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

# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
# MAPLE - Multi Agent Protocol Language Engine

import re
from typing import List, Dict, Set, Optional
from dataclasses import dataclass
from ..core.result import Result
from .registry import AgentInfo


@dataclass
class CapabilityMatch:
    """Represents a capability match between requirements and agent capabilities."""
    agent_id: str
    agent_name: str
    matched_capabilities: List[str]
    match_score: float  # 0.0 to 1.0
    load_factor: float  # Current agent load
    availability_score: float  # Combined score including load


@dataclass
class CapabilityRequirement:
    """Represents a capability requirement."""
    capability: str
    required: bool = True  # True for required, False for optional
    weight: float = 1.0  # Weight for scoring
    parameters: Dict = None  # Additional parameters for matching


class CapabilityMatcher:
    """Advanced capability matching and validation system."""
    
    def __init__(self):
        self._capability_patterns: Dict[str, str] = {}  # capability -> regex pattern
        self._capability_weights: Dict[str, float] = {}  # capability -> default weight
    
    def register_capability_pattern(self, capability: str, pattern: str, weight: float = 1.0):
        """Register a regex pattern for capability matching."""
        self._capability_patterns[capability] = pattern
        self._capability_weights[capability] = weight
    
    def match_capabilities(
        self,
        requirements: List[CapabilityRequirement],
        agents: List[AgentInfo],
        max_load_threshold: float = 0.8
    ) -> Result[List[CapabilityMatch], str]:
        """Match capability requirements against available agents."""
        
        if not requirements:
            return Result.err("No capability requirements specified")
        
        if not agents:
            return Result.err("No agents available for matching")
        
        matches = []
        
        for agent in agents:
            # Skip agents that are offline or overloaded
            if agent.status == "offline" or agent.load > max_load_threshold:
                continue
            
            match_result = self._evaluate_agent_match(requirements, agent)
            if match_result.is_ok():
                match = match_result.unwrap()
                if match.match_score > 0:
                    matches.append(match)
        
        # Sort by availability score (higher is better)
        matches.sort(key=lambda m: m.availability_score, reverse=True)
        
        return Result.ok(matches)
    
    def _evaluate_agent_match(
        self,
        requirements: List[CapabilityRequirement],
        agent: AgentInfo
    ) -> Result[CapabilityMatch, str]:
        """Evaluate how well an agent matches the requirements."""
        
        matched_capabilities = []
        required_matches = 0
        required_count = 0
        total_weight = 0.0
        matched_weight = 0.0
        
        for req in requirements:
            if req.required:
                required_count += 1
            
            total_weight += req.weight
            
            # Check if agent has this capability
            has_capability = self._check_capability_match(req.capability, agent.capabilities)
            
            if has_capability:
                matched_capabilities.append(req.capability)
                matched_weight += req.weight
                
                if req.required:
                    required_matches += 1
        
        # Must match all required capabilities
        if required_count > 0 and required_matches < required_count:
            return Result.ok(CapabilityMatch(
                agent_id=agent.agent_id,
                agent_name=agent.name,
                matched_capabilities=matched_capabilities,
                match_score=0.0,  # Failed required check
                load_factor=agent.load,
                availability_score=0.0
            ))
        
        # Calculate match score
        match_score = matched_weight / total_weight if total_weight > 0 else 0.0
        
        # Calculate availability score (considers both match and load)
        load_penalty = min(agent.load / 0.8, 1.0)  # Penalty increases as load approaches 80%
        availability_score = match_score * (1.0 - load_penalty * 0.5)
        
        return Result.ok(CapabilityMatch(
            agent_id=agent.agent_id,
            agent_name=agent.name,
            matched_capabilities=matched_capabilities,
            match_score=match_score,
            load_factor=agent.load,
            availability_score=availability_score
        ))
    
    def _check_capability_match(self, required_capability: str, agent_capabilities: List[str]) -> bool:
        """Check if an agent has a required capability."""
        
        # Direct match
        if required_capability in agent_capabilities:
            return True
        
        # Pattern matching if registered
        if required_capability in self._capability_patterns:
            pattern = self._capability_patterns[required_capability]
            for capability in agent_capabilities:
                if re.match(pattern, capability):
                    return True
        
        # Hierarchical matching (e.g., "nlp.sentiment" matches "nlp.sentiment.analysis")
        for capability in agent_capabilities:
            if capability.startswith(required_capability + "."):
                return True
            if required_capability.startswith(capability + "."):
                return True
        
        return False
    
    def validate_capability_format(self, capability: str) -> Result[bool, str]:
        """Validate that a capability string follows the expected format."""
        
        # Basic format validation
        if not capability:
            return Result.err("Capability cannot be empty")
        
        if not isinstance(capability, str):
            return Result.err("Capability must be a string")
        
        # Check for valid characters (alphanumeric, dots, hyphens, underscores)
        if not re.match(r'^[a-zA-Z0-9._-]+$', capability):
            return Result.err("Capability contains invalid characters")
        
        # Check length
        if len(capability) > 100:
            return Result.err("Capability name too long (max 100 characters)")
        
        if len(capability) < 2:
            return Result.err("Capability name too short (min 2 characters)")
        
        return Result.ok(True)
    
    def suggest_capabilities(self, partial: str, available_capabilities: Set[str]) -> List[str]:
        """Suggest capabilities based on partial input."""
        
        if not partial:
            return sorted(available_capabilities)
        
        suggestions = []
        partial_lower = partial.lower()
        
        for capability in available_capabilities:
            capability_lower = capability.lower()
            
            # Exact prefix match
            if capability_lower.startswith(partial_lower):
                suggestions.append(capability)
            # Contains match
            elif partial_lower in capability_lower:
                suggestions.append(capability)
        
        return sorted(suggestions)
    
    def get_capability_compatibility_matrix(self, agents: List[AgentInfo]) -> Dict[str, Dict[str, bool]]:
        """Generate a compatibility matrix showing which agents have which capabilities."""
        
        # Collect all unique capabilities
        all_capabilities = set()
        for agent in agents:
            all_capabilities.update(agent.capabilities)
        
        matrix = {}
        for capability in sorted(all_capabilities):
            matrix[capability] = {}
            for agent in agents:
                matrix[capability][agent.agent_id] = capability in agent.capabilities
        
        return matrix
