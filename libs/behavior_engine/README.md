# Behavior Engine

A lightweight runtime for defining, registering, and executing behaviors in Python.

A behavior is a reusable unit of activity that runs over time and yields control back to the scheduler. In this package, a behavior can be either:

- a generator function that yields `BehaviorAction` values, or
- an `AbstractBehavior` subclass with `setup()` and `tick()` methods.

This package supports both generator-style behaviors and `AbstractBehavior` subclasses, and provides a simple registry-based API with a shared execution context.

## Key concepts

- `BehaviorEngine`: high-level manager that holds a registry and executor.
- `BehaviorRegistry`: stores named behaviors and optional groups.
- `BehaviorExecutor`: schedules and runs active behavior instances.
- `BehaviorContext`: shared runtime context passed into every behavior.
- `BehaviorAction`: helper actions such as `sleep`, `stop`, and `continue`.

## Quick start

```python
from behavior_engine import BehaviorAction, BehaviorContext, BehaviorEngine, AbstractBehavior

class DemoContext(BehaviorContext):
    def __init__(self):
        self.count = 0


def blink(ctx: DemoContext):
    while ctx.count < 3:
        print(f"Blink {ctx.count + 1}")
        ctx.count += 1
        yield BehaviorAction.sleep(0.5)
    yield BehaviorAction.stop()

engine = BehaviorEngine(DemoContext())
engine.load_behavior("blink", blink)
engine.play_behavior("blink")

while engine.running_behaviors():
    engine.tick()
```

## Examples

A working example is provided in `examples/simple_usage.py`.

Run it from the package directory:

```bash
python examples/simple_usage.py
```

## API overview

- `load_behavior(name, behavior, groups=None, **metadata)`: register a behavior.
- `play_behavior(name, priority=0)`: start a registered behavior.
- `tick()`: advance all active behaviors.
- `stop_behavior(name)`: stop a running behavior.
- `stop_all()`: stop every behavior currently running.

## Why use it

This package is useful when you want a small, explicit behavior scheduler for robotics, simulation, or simple AI systems. It keeps behavior definitions decoupled from execution details, and makes it easy to group and manage reusable behaviors.
