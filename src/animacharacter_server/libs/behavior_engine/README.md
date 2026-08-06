# Behavior Engine

A simple Python package for defining, registering, and executing runtime behaviors.

This package was built for the Animacharacter Engine, a ROS2-based system that uses behaviors to add custom functionality to robots. It provides a behavior context interface designed for direct interaction with the otherwise hidden ROS2-based systems.

## What this package does

This package provides:

- a registry for storing named behaviors and group labels,
- a scheduler to run behaviors,
- a shared customizable `BehaviorContext` object passed into every behavior,
- a built-in publish/subscribe system for behavior-to-behavior messaging,
- decorators and dynamic loading of behaviors utilities for external plugin modules.

## What is a behavior?

A behavior is a unit of work that runs over time, yields control back to the scheduler, and can stop when finished. Behaviors are intended for logic that needs to be executed in the background to add custom functionality to a system.

A behavior can be one of two forms:

1. a generator function that receives a `BehaviorContext` and yields `BehaviorAction` values,
2. an `AbstractBehavior` subclass that defines `setup()` and `tick()` methods.

## Core concepts

### BehaviorEngine

`BehaviorEngine` is the main higher-level class.

It holds:

- a registry of known behaviors,
- an executor for running active behaviors,
- a list of currently running behavior instances.

### BehaviorRegistry

`BehaviorRegistry` stores behaviors by name and optional group labels.

You can load a behavior once and borrow it later by name.

### BehaviorExecutor

`BehaviorExecutor` runs active behaviors in priority order and advances them on each `tick()`.

### BehaviorContext

`BehaviorContext` is the shared object passed into every behavior.

The default context includes:

- publisher/subscriber support for message passing,
- helper methods to create publishers and subscribers.

Use it to store runtime data or exchange messages between behaviors, and subclass it
to create a custom interface for behaviors to interact with your external system.

### Plugin loading

The package includes a small plugin utility for loading behaviors from external Python modules.

A plugin module can define behaviors using the `@behavior(name, groups=None, **metadata)` decorator.

Available plugin helpers:

- `discover_behaviors(module)`: find decorated behaviors in a loaded module,
- `load_behaviors_from_module(engine, module)`: register those behaviors with an engine,
- `load_behaviors_from_file(engine, path)`: import a single plugin file dynamically,
- `load_behaviors_from_directory(engine, directory, pattern="*.py")`: import all plugin files from a directory.

Plugin loading is separate from the engine core, so the same runtime API remains unchanged.

## How behaviors work

### Generator-style behavior

A generator-style behavior is a function that looks like this:

```python
from behavior_engine import BehaviorAction, BehaviorContext

class DemoContext(BehaviorContext):
    def __init__(self):
        self.count = 0


def blink(ctx: DemoContext):
    while ctx.count < 3:
        print(f"Blink {ctx.count + 1}")
        ctx.count += 1
        yield BehaviorAction.sleep(0.5)
    yield BehaviorAction.stop()
```

Each time the scheduler advances the behavior, the function runs until the next `yield`.

### AbstractBehavior subclass

An `AbstractBehavior` subclass separates setup from repeated ticks:

```python
from behavior_engine import AbstractBehavior, BehaviorAction

class SayHelloBehavior(AbstractBehavior[DemoContext]):
    def setup(self):
        return BehaviorAction.continue_()

    def tick(self):
        print("Hello")
        return BehaviorAction.stop()
```

Use this form when you want a class-based behavior with state and explicit setup.

## Context and messaging

The default `BehaviorContext` provides a publish/subscribe pattern.

Behaviors can create publishers and subscribers for named topics:

```python
sensor = ctx.create_publisher("sensor")
actuator = ctx.create_subscriber("sensor")
```

When a behavior publishes a message, all subscribers on that topic receive it.

This is useful when behaviors need to exchange data without directly calling each other.

## Example usage

```python
from behavior_engine import BehaviorAction, BehaviorContext, BehaviorEngine

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

## Installation

Install from the package directory:

```bash
cd src/animacharacter_server/libs/behavior_engine
pip install -e .
```

## Running the example

A working example is available in `examples/simple_usage.py`.

A plugin loader example is available in `examples/plugin_usage.py` and uses `examples/plugin_module.py`.

Run it from the package directory:

```bash
python examples/simple_usage.py
```

```bash
python examples/plugin_usage.py
```

## API summary

- `BehaviorEngine.load_behavior(name, behavior, groups=None, **metadata)`: register a behavior under a name.
- `BehaviorEngine.play_behavior(name, priority=0)`: start a registered behavior.
- `BehaviorEngine.play_behavior_group(group, priority=0)`: start all behaviors in a group.
- `BehaviorEngine.tick()`: advance all running behaviors one scheduler step.
- `BehaviorEngine.stop_behavior(name)`: stop a running behavior.
- `BehaviorEngine.stop_all()`: stop every behavior currently running.
- `BehaviorEngine.running_behaviors()`: get a list of active behavior names.
- `BehaviorEngine.loaded_behaviors()`: get a list of registered behaviors.
- `behavior(name, groups=None, **metadata)`: decorator for plugin behaviors.
- `load_behaviors_from_module(engine, module)`: register decorated behaviors from a loaded module.
- `load_behaviors_from_file(engine, path)`: import a plugin file and register its behaviors.
- `load_behaviors_from_directory(engine, directory, pattern="*.py")`: import all plugin files in a folder.