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


# maple/broker/production_broker.py
# Creator: Mahesh Vaikri

"""
Production Broker Manager for MAPLE
Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
"""

from enum import Enum
from typing import Dict, Any, Optional, Union
from ..core.result import Result

class BrokerType(Enum):
    """Available broker types."""
    IN_MEMORY = "in_memory"
    NATS = "nats"
    REDIS = "redis"
    RABBITMQ = "rabbitmq"

class ProductionBrokerManager:
    """Manages production broker instances."""
    
    @staticmethod
    def get_available_brokers() -> Dict[BrokerType, bool]:
        """Get available broker types."""
        return {
            BrokerType.IN_MEMORY: True,
            BrokerType.NATS: False,  # Would check for nats-py
            BrokerType.REDIS: False,  # Would check for redis-py
            BrokerType.RABBITMQ: False  # Would check for pika
        }
    
    @staticmethod
    def create_broker(config, preferred_type: BrokerType = BrokerType.IN_MEMORY) -> Result[Any, Dict[str, Any]]:
        """Create a broker instance."""
        try:
            if preferred_type == BrokerType.IN_MEMORY:
                from .broker import MessageBroker
                broker = MessageBroker(config)
                return Result.ok(broker)
            else:
                return Result.err({
                    'errorType': 'BROKER_UNAVAILABLE',
                    'message': f'Broker type {preferred_type.value} not available'
                })
        except Exception as e:
            return Result.err({
                'errorType': 'BROKER_CREATION_ERROR',
                'message': str(e)
            })

def create_production_broker(config, preferred_type: BrokerType = BrokerType.IN_MEMORY):
    """
    Create a production broker instance.
    
    Args:
        config: Agent configuration
        preferred_type: Preferred broker type
    
    Returns:
        Result containing broker instance or error
    """
    return ProductionBrokerManager.create_broker(config, preferred_type)
