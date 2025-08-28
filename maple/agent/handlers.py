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


# maple/agent/handlers.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

from typing import Callable, Optional, Dict, Any
from ..core.message import Message
from ..core.result import Result

class MessageHandler:
    """
    Base class for message handlers.
    """
    
    def __init__(self, message_type: str, handler_func: Callable[[Message], Optional[Message]]):
        self.message_type = message_type
        self.handler_func = handler_func
    
    def can_handle(self, message: Message) -> bool:
        """
        Check if this handler can handle the message.
        
        Args:
            message: The message to check
            
        Returns:
            True if this handler can handle the message
        """
        return message.message_type == self.message_type
    
    def handle(self, message: Message) -> Result[Optional[Message], Dict[str, Any]]:
        """
        Handle a message.
        
        Args:
            message: The message to handle
            
        Returns:
            Result containing optional response message or error
        """
        try:
            response = self.handler_func(message)
            return Result.ok(response)
        except Exception as e:
            return Result.err({
                'errorType': 'HANDLER_ERROR',
                'message': f'Error in message handler: {str(e)}',
                'details': {
                    'messageType': message.message_type,
                    'handlerType': self.message_type
                }
            })

class HandlerRegistry:
    """
    Registry for message handlers.
    """
    
    def __init__(self):
        self.handlers = {}
    
    def register(self, message_type: str, handler: Callable[[Message], Optional[Message]]) -> None:
        """
        Register a handler for a message type.
        
        Args:
            message_type: The message type to handle
            handler: The handler function
        """
        self.handlers[message_type] = MessageHandler(message_type, handler)
    
    def get_handler(self, message_type: str) -> Optional[MessageHandler]:
        """
        Get a handler for a message type.
        
        Args:
            message_type: The message type
            
        Returns:
            The handler if found, None otherwise
        """
        return self.handlers.get(message_type)
    
    def handle_message(self, message: Message) -> Result[Optional[Message], Dict[str, Any]]:
        """
        Handle a message using the appropriate handler.
        
        Args:
            message: The message to handle
            
        Returns:
            Result containing optional response message or error
        """
        handler = self.get_handler(message.message_type)
        if handler:
            return handler.handle(message)
        
        return Result.err({
            'errorType': 'NO_HANDLER',
            'message': f'No handler found for message type: {message.message_type}'
        })
    
    def list_handlers(self) -> list:
        """Get a list of all registered message types."""
        return list(self.handlers.keys())
