"""Managed state machine, fault recovery, and reconciler for stateful components.

This package models the lifecycle of a component or hardware driver (such as a device
connection, worker, or controller) and drives it toward a desired target state without
requiring callers to manually sequence every state transition.

Core Concepts
-------------
- **Lifecycle states (`State`)**: A component starts in ``UNCONFIGURED``, moves through
  ``INACTIVE`` and ``ACTIVE``, and ends in ``FINALIZED``. It can also enter ``FAULTED``
  when a transition or active execution step fails with an error or unhandled exception.
- **Transitions & FSM structure (`TransitionId`)**: Standard transitions move the
  component between states as follows:
  - ``AWAKE``: ``UNCONFIGURED`` -> ``INACTIVE``
  - ``ACTIVATE``: ``INACTIVE`` -> ``ACTIVE``
  - ``DEACTIVATE``: ``ACTIVE`` -> ``INACTIVE``
  - ``SHUTDOWN``: ``INACTIVE`` -> ``FINALIZED``
  - ``RUN``: ``ACTIVE`` -> ``ACTIVE`` (self-transition executed repeatedly while active)

- **Component hooks (`Lifecyclable`)**: Implement this abstract base class to define what
  your component does on each lifecycle transition (``on_awake``, ``on_activate``,
  ``on_deactivate``, ``on_shutdown``), during active execution (``on_run``), and during
  error recovery (``on_recover``).
- **Stateful wrapper (`LifecyclableWrapper`)**: Makes a ``Lifecyclable`` instancle usable by turning it into a
  stateful object. Tracks its current state and active fault information, and exposes
  methods (``transition``, ``run``, ``run_recover``) to invoke hooks and enforce valid
  state changes.
- **Faults and recovery (`FAULTED`, `on_recover`, `RecoveryResult`)**: When a transition
  hook (including ``on_run``) returns ``TransitionResult.ERROR`` or raises an exception, the
  component's actual state can no longer be assumed consistent with the normal state
  machine. Entering ``FAULTED`` suspends standard transition assumptions and delegates
  control to ``on_recover``. ``on_recover`` allows you to inspect the fault context,
  restore hardware or internal resources to a known condition, and return a
  ``RecoveryResult`` specifying the new state so normal operation can resume.
- **Single-step reconciliation (`reconcile_step`, `recoincile`, `BackoffConfig`)**:
  Advances a ``LifecyclableWrapper`` by at most one step toward a target state (or runs
  one recovery attempt if ``FAULTED``) and computes retry/recovery backoff delays when a
  step cannot advance immediately. The new state can also be ``FINALIZED``, meaning the component
  is in a safe, recovedered, finalized state.
- **Lifecycle runner (`LifecycleRunner`)**: Instantiates a ``LifecyclableWrapper`` for a
  provided ``Lifecyclable`` object and drives it toward a mutable target state set via
  ``set_target_state(...)``. While ``ACTIVE`` at the target state, it repeatedly invokes
  ``run()``; when idle at another target state, it waits without busy-polling until the
  target changes; once ``FINALIZED`` is reached, ``run()`` exits. Although
  ``LifecycleRunner`` is not threaded by itself, ``run()`` is designed so it can be
  executed inside a dedicated thread while ``set_target_state(...)`` is called from
  another thread.

Typical Usage
-------------
1. Subclass ``Lifecyclable`` and implement its lifecycle, execution, and recovery hooks.
2. Pass your ``Lifecyclable`` instance to ``LifecycleRunner`` (which creates and manages
   the ``LifecyclableWrapper`` internally).
3. Run ``runner.run()``—optionally in a background thread—and call
   ``runner.set_target_state(...)`` (for example, ``State.INACTIVE`` to pause or
   ``State.FINALIZED`` to shut down) to control the lifecycle.
"""

from .hooks import Lifecyclable, get_hook_from_transition_id
from .reconcile import (
    BackoffConfig,
    DEFAULT_BACKOFF_CONFIG,
    ReconcileOutcome,
    reconcile_step,
)
from .routing import (
    NEXT_TRANSITION_MAP,
    TRANSITION_MAP,
    VALID_TARGET_STATES,
)
from .runner import LifecycleRunner
from .types import (
    FaultContext,
    RecoveryResult,
    RecoveryResultStatus,
    State,
    TransitionId,
    TransitionResult,
)
from .wrapper import LifecyclableWrapper

__all__ = [
    "State",
    "TransitionId",
    "TransitionResult",
    "RecoveryResultStatus",
    "RecoveryResult",
    "FaultContext",
    "TRANSITION_MAP",
    "VALID_TARGET_STATES",
    "NEXT_TRANSITION_MAP",
    "Lifecyclable",
    "get_hook_from_transition_id",
    "LifecyclableWrapper",
    "BackoffConfig",
    "DEFAULT_BACKOFF_CONFIG",
    "ReconcileOutcome",
    "reconcile_step",
    "LifecycleRunner",
]
