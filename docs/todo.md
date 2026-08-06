
- client:
  - test more
  - refine api
  - test test test

- session manager:
  - rely more on native async implementation of nodes and executors
  - implement lifecycle transitions
    - active: clients connections are possible
    - non-active: clients connections interrupted

- orchestration:
  - integrate other nodes (respawnable processes)
    - abstract respawnable process tracking into objects
  - missing nodes:
    - webUI (can also be ignored for now)

- architecture:

  ##########- system topics:
  ##########  - /system_alerts type
  ##########  - /system_status ?
  ##########    - do we redirect all alerts on system status to be shown on display? 
  ##########    system status is behaving more like an alert
  
  - datapath from server to client:
    - needs to be versatile
    - what do we need?
    - does it make sense to allow hardware drivers to publish to client?

  - rename "configs" to "datatree"?
    - more generic
    - less explicit about its original goal

  - swap out the "Motionframes" topic for a unix socket? much faster in theory

- documentation:
  - document plugin usage

- hardware:
  - status panel
  - reprogram head entirely
  - body electronics
    - still have to decide on head rotation motor
  
