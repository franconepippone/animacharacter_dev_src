from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from .proto_logger import LoggerLike, StupidLogger

CtxT = TypeVar("CtxT")



class SessionCreationError(Exception):
    """Custom exception for errors during session creation."""


class SessionDestructionError(Exception):
    """Custom exception for errors during session destruction."""


@dataclass
class SessionCreationResult(Generic[CtxT]):
    """Result of a session creation attempt."""
    success: bool
    context: CtxT | None
    exception_on_creation: Exception | None = None

    def __bool__(self) -> bool:
        return self.success


@dataclass
class SessionDestructionResult:
    """Result of a session destruction attempt."""
    success: bool
    exception_on_destruction: Exception | None = None

    def __bool__(self) -> bool:
        return self.success


class SessionResourceManager(Generic[CtxT], ABC):
    """Abstract base class for managing a session context lifecycle."""

    def __init__(self, logger: LoggerLike | None = None) -> None:
        self.logger = logger if logger is not None else StupidLogger()

    def create_session(self) -> SessionCreationResult[CtxT]:
        """Create a session context and return the result object."""
        try:
            context = self.create()
            if context is None:
                raise SessionCreationError("Session creation failed: 'create' returned None.")
            self.logger.info("Session created successfully.")
            return SessionCreationResult(success=True, context=context)
        except SessionCreationError as exc:
            self.logger.error(f"Session creation failed: {exc}")
            return SessionCreationResult(success=False, context=None, exception_on_creation=exc)
        except Exception as exc:
            self.logger.error(f"An unexpected exception was raised during session creation: {exc}")
            return SessionCreationResult(success=False, context=None, exception_on_creation=exc)
    
    def destroy_session(self, context: CtxT) -> SessionDestructionResult:
        """Destroy a session context and return a SessionDestructionResult object."""
        try:
            self.destroy(context)
            self.logger.info("Session destroyed successfully.")
            return SessionDestructionResult(success=True)
        except SessionDestructionError as exc:
            self.logger.error(f"Session destruction failed: {exc}")
            return SessionDestructionResult(success=False, exception_on_destruction=exc)
        except Exception as exc:
            self.logger.error(f"An unexpected exception was raised during session destruction: {exc}")
            return SessionDestructionResult(success=False, exception_on_destruction=exc)

    @abstractmethod
    def destroy(self, context: CtxT) -> None:
        """Release resources owned by the provided session context."""

    @abstractmethod
    def create(self) -> CtxT:
        """Construct and return a valid session context."""
        
