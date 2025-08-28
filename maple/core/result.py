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


# maple/core/result.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

from typing import Generic, TypeVar, Union, Callable, Optional

T = TypeVar('T')
E = TypeVar('E')
U = TypeVar('U')
F = TypeVar('F')

class Result(Generic[T, E]):
    """
    A type that represents either success (Ok) or failure (Err).
    """
    
    def __init__(self, is_ok: bool, value: Union[T, E]):
        self._is_ok = is_ok
        self._value = value
    
    @classmethod
    def ok(cls, value: T) -> 'Result[T, E]':
        """Create a new Ok result."""
        return cls(True, value)
    
    @classmethod
    def err(cls, error: E) -> 'Result[T, E]':
        """Create a new Err result."""
        return cls(False, error)
    
    def is_ok(self) -> bool:
        """Check if the result is Ok."""
        return self._is_ok
    
    def is_err(self) -> bool:
        """Check if the result is Err."""
        return not self._is_ok
    
    def unwrap(self) -> T:
        """
        Extract the success value or raise an exception.
        
        Raises:
            Exception: If the result is Err.
        """
        if self._is_ok:
            return self._value
        raise Exception(f"Called unwrap on an Err value: {self._value}")
    
    def unwrap_or(self, default: T) -> T:
        """Extract the success value or return a default."""
        if self._is_ok:
            return self._value
        return default
    
    def unwrap_err(self) -> E:
        """
        Extract the error value or raise an exception.
        
        Raises:
            Exception: If the result is Ok.
        """
        if not self._is_ok:
            return self._value
        raise Exception(f"Called unwrap_err on an Ok value: {self._value}")
    
    def map(self, f: Callable[[T], U]) -> 'Result[U, E]':
        """Apply a function to the success value."""
        if self._is_ok:
            return Result.ok(f(self._value))
        return Result.err(self._value)
    
    def map_err(self, f: Callable[[E], F]) -> 'Result[T, F]':
        """Apply a function to the error value."""
        if not self._is_ok:
            return Result.err(f(self._value))
        return Result.ok(self._value)
    
    def and_then(self, f: Callable[[T], 'Result[U, E]']) -> 'Result[U, E]':
        """Chain operations that might fail."""
        if self._is_ok:
            return f(self._value)
        return Result.err(self._value)
    
    def or_else(self, f: Callable[[E], 'Result[T, F]']) -> 'Result[T, F]':
        """Provide an alternative if the result is an error."""
        if not self._is_ok:
            return f(self._value)
        return Result.ok(self._value)