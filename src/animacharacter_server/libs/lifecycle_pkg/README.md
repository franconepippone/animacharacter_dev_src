
```mermaid
flowchart LR
    START(( )) --> UNCONFIGURED
    UNCONFIGURED -->|AWAKE| INACTIVE
    INACTIVE <-->|"ACTIVATE / DEACTIVATE"| ACTIVE
    ACTIVE -->|RUN| ACTIVE
    INACTIVE -->|SHUTDOWN| FINALIZED
    FINALIZED --> END(( ))

    UNCONFIGURED -.->|"ERROR / exc"| FAULTED
    INACTIVE -.->|"ERROR / exc"| FAULTED
    ACTIVE -.->|"ERROR / exc"| FAULTED

    FAULTED -.->|"on_recover: SUCCESS(state)"| UNCONFIGURED
    FAULTED -.->|"on_recover: SUCCESS(state)"| INACTIVE
    FAULTED -.->|"on_recover: SUCCESS(state)"| ACTIVE
    FAULTED -.->|"on_recover: SUCCESS(state)"| FINALIZED
```

`LifecycleRunner` accepts an optional `event_sink` for lifecycle and target-state
events. Events are dispatched asynchronously; a full event queue drops new events
rather than delaying lifecycle work. Use `NullEventSink` (the default),
`StdlibLoggingSink`, or `FanOutEventSink` to select how events are consumed.