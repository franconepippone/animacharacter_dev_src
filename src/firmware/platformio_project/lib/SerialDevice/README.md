**SerialDevice — PlatformIO / Arduino library (C++)**

Scope
- This library (`lib/SerialDevice`) provides a Arduino/PlatformIO class that sits on top
  of the `SerialTransfer` library, and presents a packet-oriented API and a higher-level functionalities, such as pinging and device discovery.
  It is designed to be used on microcontrollers that support Arduino-style `HardwareSerial`.

What it can do
- Receive and dispatch packets using registered callbacks (`on(packetId, handler)`) or a fallback
  handler for any packet.
- Request peer identity and send identity responses.
- Send/receive packets using `sendPacket`, `sendBytes`, `recvPacket`, and `recvBytes` methods.
- Support large transfers: automatic fragmentation on send (`sendLarge`) and reassembly on receive
  with timeout and acknowledgement semantics.

Key API
- Include and construct:
```cpp
  #include "SerialDevice.h"
  HardwareSerial& hw = Serial1;              // or Serial
  SerialDevice dev(hw, "my_device");
```
- Initialize serial port:
```cpp
  dev.begin(115200);
```
- Register handlers (callbacks are simple functions):
```cpp
  dev.on(PACKID_IDENT_RQST, myIdentHandler);
  dev.onAny(myAnyHandler);
```
- Send small packets:
```cpp
  dev.sendPacket("hello", PACKID_DIAGNOSTIC);
  dev.sendBytes(buffer, size, PACKID_SOMEID);
```
- Send a large buffer (fragments internally):
```cpp
  dev.sendLarge(buffer, bufferSize, PACKID_DEV_INFO_RESP, timeoutMs, chunkSize);
```
- Poll for incoming data and dispatch to callbacks:
```cpp
  dev.poll();   // calls callbacks registered with on()
```
Protocol notes and constants
- Reserved packet IDs from 200-20.
- A small built-in testing framework exists (triggerable IDs 220/221), used only for testing.

Usage example (sketch)
```cpp
  #include <Arduino.h>
  #include <SerialDevice.h>

  #define MY_PACK_ID 15

  // we create memory to recv our packet into
  struct __attribute__((packed)) {
    bool a;
    uint32_t b;
    float c;
  } myPackBuffer;


  SerialDevice dev(Serial, "board_alpha");
  
  bool myPackHandler(SerialDevice* d) {
    d->recvBytes(myPackBuffer);
    return false; // always return false to consume the packet
  }


  void setup() {
    dev.begin(115200);
    // bind handler / callback
    dev.on(MY_PACK_ID, myPackHandler);
  }

  void loop() {
    dev.poll();
    // perform application tasks
  }
```
Notes
- The library uses `SerialTransfer` internally, and expects callers to provide a receive
  buffer for large transfers via `configLargeRx()` if they want to handle large incoming payloads.
