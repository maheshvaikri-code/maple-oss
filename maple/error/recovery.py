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


# mapl/error/recovery.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

from typing import Dict, Any, Optional, Callable, TypeVar, Generic
import time
import logging
import random
from dataclasses import dataclass

from ..core.result import Result

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

T = TypeVar('T')
E = TypeVar('E')

@dataclass
class RetryOptions:
    """Options for retry operations."""
    max_attempts: int = 3
    backoff: Callable[[int], float] = lambda attempt: 0.1 * (2 ** attempt)  # Exponential backoff
    retryable_errors: Optional[list] = None  # None means retry all errors

def retry(func: Callable[[], Result[T, E]], options: RetryOptions) -> Result[T, E]:
    """
    Retry a function with the specified options.
    
    Args:
        func: The function to retry.
        options: Options for retrying.
    
    Returns:
        The result of the function, or the last error if all attempts fail.
    """
    attempt = 0
    last_error = None
    
    while attempt < options.max_attempts:
        # Execute the function
        result = func()
        
        # If successful, return the result
        if result.is_ok():
            return result
        
        # If not successful, check if we should retry
        error = result.unwrap_err()
        last_error = error
        
        # Check if this error is retryable
        if options.retryable_errors is not None:
            error_type = error.get('errorType', 'UNKNOWN_ERROR') if isinstance(error, dict) else str(type(error))
            if error_type not in options.retryable_errors:
                logger.debug(f"Error {error_type} is not retryable, giving up")
                return result
        
        # If we've reached the maximum attempts, give up
        attempt += 1
        if attempt >= options.max_attempts:
            logger.debug(f"Maximum retry attempts ({options.max_attempts}) reached, giving up")
            return result
        
        # Calculate backoff time
        delay = options.backoff(attempt)
        
        logger.debug(f"Retrying after {delay}s (attempt {attempt}/{options.max_attempts})")
        time.sleep(delay)
    
    # This should never be reached, but just in case
    return Result.err(last_error)

def exponential_backoff(initial: float = 0.1, factor: float = 2.0, jitter: float = 0.1) -> Callable[[int], float]:
    """
    Create an exponential backoff function.
    
    Args:
        initial: Initial delay in seconds.
        factor: Multiplication factor for each attempt.
        jitter: Random jitter factor (0-1) to add to the delay.
    
    Returns:
        A function that calculates the delay for each attempt.
    """
    def backoff(attempt: int) -> float:
        delay = initial * (factor ** attempt)
        if jitter > 0:
            delay += delay * random.uniform(0, jitter)
        return delay
    
    return backoff