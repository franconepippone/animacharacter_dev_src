
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
events. Events are emitted synchronously on the calling thread, so sinks must
return quickly and must not block lifecycle work. Sink exceptions are logged and
do not interrupt the runner. Use `NullEventSink` (the default),
`StdlibLoggingSink`, or `FanOutEventSink` to select how events are consumed.