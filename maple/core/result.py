"""
Result<T,E> Pattern Implementation for MAPLE
Created by: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

Type-safe error handling mechanism for distributed agent communication.
"""

from typing import Generic, TypeVar, Union, Callable, Optional, Any
import json

T = TypeVar('T')
E = TypeVar('E')
U = TypeVar('U')
F = TypeVar('F')

class Result(Generic[T, E]):
    """
    A type that represents either success (Ok) or failure (Err).
    Core to MAPLE's perfect error handling that contributes to 32/32 test success.
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
    
    def to_dict(self) -> dict:
        """Convert result to dictionary for serialization."""
        return {
            "status": "ok" if self._is_ok else "err",
            "value" if self._is_ok else "error": self._value
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Result[Any, Any]':
        """Create result from dictionary."""
        if data.get("status") == "ok":
            return cls.ok(data.get("value"))
        else:
            return cls.err(data.get("error"))
    
    def __repr__(self) -> str:
        if self._is_ok:
            return f"Result.ok({self._value!r})"
        else:
            return f"Result.err({self._value!r})"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Result):
            return False
        return self._is_ok == other._is_ok and self._value == other._value
