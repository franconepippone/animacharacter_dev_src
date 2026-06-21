# Animacharacter Platform

Animacharacter Platform is a framework for remotely controlling hardware systems composed of many controllable elements.

The primary goal of the project is to provide a standard architecture that separates application logic from hardware-specific implementation details.

The main target use case is animatronics, where a platform may consist of dozens of motors, LEDs, sensors, and microcontrollers. However, the framework can be used in any system where a single process needs to coordinate a large number of distributed devices.

## The Problem

In real-world systems, different devices are often connected through different hardware interfaces and communication protocols.

For example:

```text
Application
 ├─> Arduino (Serial)
 ├─> Motor Driver (SPI)
 ├─> LED Controller
 └─> ...
```

As the system grows, application code tends to accumulate hardware-specific logic, making it increasingly difficult to maintain, extend, or replace parts of the platform.

## The Idea

Animacharacter Platform introduces an intermediate layer between the application and the hardware.

The application simply describes the desired state of the platform; the framework is responsible for transporting commands, routing them, and translating them into operations that can be executed by the underlying hardware.

```text
Application
      ↓
Animacharacter Platform
      ↓
Hardware
```

This allows hardware implementations to evolve independently from the software that controls them.

## Architecture

The system consists of two main components.

### Client

The Client is a Python library used by applications.

It exposes a hierarchical representation of the hardware platform and provides a high-level API for modifying its state.

Example:

```python
robot.head.left_eye.pan.value = 10
robot.body.rotation.value = 30
```

The application does not need to know how these values are transmitted or which physical devices will ultimately execute them.

### Engine

The Engine is the process responsible for receiving commands from clients and distributing them to the components that interact with the hardware.

```text
Client
   ↓
Engine
   ↓
Hardware
```

The Engine is typically deployed on an onboard computer such as a Raspberry Pi.

## Extensibility

Hardware integration is implemented through dynamically loaded Python plugins.

Each plugin defines:

* which parts of the platform it manages;
* how it communicates with the associated hardware;
* any control or coordination logic required by that hardware.

This approach makes it possible to support different devices and communication protocols without modifying the core framework.

## Communication Model

The framework distinguishes between two categories of data.

### Control Commands

Control commands represent the desired state of the platform and are transmitted using a compact, low-latency format suitable for frequent updates.

### Configuration Data

Configuration data represents parameters, settings, and structured information that change infrequently and do not require real-time transmission.

Separating these two communication flows allows the system to handle different timing requirements efficiently.

## Project Goals

* Provide a uniform model for controlling complex hardware systems.
* Separate application logic from hardware-specific implementation details.
* Support heterogeneous devices through a plugin-based architecture.
* Scale to platforms containing many controllable elements.
* Enable coordination between subsystems while preserving modularity.

For a detailed description of the internal architecture and framework components, see the project documentation.
