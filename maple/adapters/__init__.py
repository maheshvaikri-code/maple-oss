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

# maple/adapters/__init__.py
# Creator: Mahesh Vaikri

"""
MAPLE Adapters - Integration with external platforms and protocols.
"""

# S2.dev durable streaming integration
try:
    from .s2_adapter import S2Broker, S2StateBackend, S2Config  # noqa: F401
    S2_AVAILABLE = True
except ImportError:  # pragma: no cover
    S2_AVAILABLE = False
