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


# mapl/error/circuit_breaker.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

from enum import Enum
from typing import Dict, Any, Optional, Callable, TypeVar, Generic
import time
import threading
import logging

from ..core.result import Result

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

T = TypeVar('T')
E = TypeVar('E')

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"  # Normal operation, requests allowed
    OPEN = "OPEN"      # Circuit is open, requests blocked
    HALF_OPEN = "HALF_OPEN"  # Testing if the circuit can be closed again

class CircuitBreaker(Generic[T, E]):
    """
    Circuit breaker pattern implementation.
    
    The circuit breaker prevents cascading failures by stopping operations
    when a service is failing, and periodically testing if it has recovered.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        half_open_max_calls: int = 1
    ):
        """
        Initialize the circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening the circuit.
            reset_timeout: Time in seconds before testing if the circuit can be closed again.
            half_open_max_calls: Maximum number of calls allowed in half-open state.
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
        
        self._lock = threading.RLock()
    
    def execute(self, func: Callable[[], Result[T, E]]) -> Result[T, E]:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: The function to execute.
        
        Returns:
            The result of the function, or an error if the circuit is open.
        """
        with self._lock:
            # Check if the circuit is open
            if self.state == CircuitState.OPEN:
                # Check if it's time to try half-open
                if time.time() - self.last_failure_time >= self.reset_timeout:
                    logger.info("Circuit half-open, testing service")
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    logger.debug(f"Circuit open, blocking request (reset in {self.reset_timeout - (time.time() - self.last_failure_time):.1f}s)")
                    return Result.err({
                        'errorType': 'CIRCUIT_OPEN',
                        'message': 'Circuit breaker is open',
                        'details': {
                            'resetTimeout': self.reset_timeout,
                            'timeRemaining': self.reset_timeout - (time.time() - self.last_failure_time)
                        }
                    })
            
            # Check if we've reached the limit of half-open calls
            if self.state == CircuitState.HALF_OPEN and self.half_open_calls >= self.half_open_max_calls:
                logger.debug("Half-open call limit reached, blocking request")
                return Result.err({
                    'errorType': 'CIRCUIT_HALF_OPEN',
                    'message': 'Circuit breaker is half-open and call limit reached',
                    'details': {
                        'maxCalls': self.half_open_max_calls
                    }
                })
            
            # Increment half-open calls if applicable
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_calls += 1
        
        # Execute the function
        result = func()
        
        with self._lock:
            if result.is_ok():
                # Success, close the circuit if it was half-open
                if self.state == CircuitState.HALF_OPEN:
                    logger.info("Service recovered, closing circuit")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                elif self.state == CircuitState.CLOSED:
                    # Reset failure count on success
                    self.failure_count = 0
            else:
                # Failure, increment failure count
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                # If we've reached the threshold, open the circuit
                if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
                    logger.warning(f"Failure threshold reached ({self.failure_count}), opening circuit")
                    self.state = CircuitState.OPEN
                
                # If we're in half-open state, go back to open
                if self.state == CircuitState.HALF_OPEN:
                    logger.info("Service still failing, reopening circuit")
                    self.state = CircuitState.OPEN
        
        return result
    
    def is_open(self) -> bool:
        """Check if the circuit is open."""
        return self.state == CircuitState.OPEN
    
    def is_closed(self) -> bool:
        """Check if the circuit is closed."""
        return self.state == CircuitState.CLOSED
    
    def is_half_open(self) -> bool:
        """Check if the circuit is half-open."""
        return self.state == CircuitState.HALF_OPEN
    
    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        with self._lock:
            logger.info("Circuit breaker manually reset to closed state")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure_time = 0
            self.half_open_calls = 0