"""
Generic session lifecycle abstractions.

This package provides reusable building blocks for managing a single session
execution flow in a background thread. It separates resource management,
session execution, and cleanup into composable components.

Contains:
- SessionResourceManager: create and destroy session contexts safely
- SessionRunner: execute a session in a background thread
- SessionHandle: returned by a SessionRunner, interface to a running session
- SessionManager: orchestrate a single active session end to end. 
    Configurable with custom resource manager and runner implementations.
"""
from .resource_manager import SessionCreationResult, SessionDestructionResult, SessionResourceManager
from .runner import SessionHandle, SessionRunner, SessionRunnerCallable, SessionCleanupCallable
from .session_manager import SessionManager, SessionStartResult