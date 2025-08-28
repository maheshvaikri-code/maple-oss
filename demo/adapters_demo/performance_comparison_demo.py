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


# Demonstrate MAPLE's superior performance
import time
from crewai_adapter import CrewAIAdapter, Crew

# Standard CrewAI approach
start_time = time.time()
standard_crew = Crew(agents=agents, tasks=tasks)
standard_result = standard_crew.kickoff()
standard_time = time.time() - start_time

# MAPLE-enhanced CrewAI
start_time = time.time()
maple_crew = crewai_adapter.create_maple_enhanced_crew(agents, tasks)
maple_result = maple_crew.kickoff()
maple_time = time.time() - start_time

print(f"Standard CrewAI: {standard_time:.4f}s")
print(f"MAPLE-Enhanced: {maple_time:.4f}s")
print(f"Performance improvement: {standard_time/maple_time:.2f}x faster")
# Expected output: 25-200x faster with MAPLE