#pragma once
#include <Arduino.h>
#include "SerialTransfer.h"

// ======================= STRUCTS / TYPEDEFS =======================

class SerialDevice;

typedef void (*PacketHandler)(SerialDevice*);
typedef void (*WidePacketHandler)(uint8_t, SerialDevice*);

// ======================= DEFAULT PACKET IDs =======================

// default packets IDs (reserved 200-220)
#define PACKID_IDENT_RQST 200
#define PACKID_IDENT_RESP 201
#define PACKID_DIAGNOSTIC 202
#define PACKID_PING 203
#define PACKID_LARGETX_BEGIN 204
#define PACKID_LARGETX_CHUNK 205
#define PACKID_ACK 206 // unused for now

// debug hooks
#define PACKID_DEBUG_TRIGGER_IDENT_RQST 210

// ======================= DEBUG FUNCTIONS =======================

// Blinks the built-in LED a number of times
void _debug_blink_builtin(int times, int period = 100);

// used to trigger device to perform a peername request (used for debugging)
void _debug_triggerIdent(SerialDevice* dev);

// ======================= DEFAULT PACK HANDLERS =======================
// Handler for ping
void handlePing(SerialDevice* dev);

// Handler for device identification protocol
void handleAuthRqst(SerialDevice* dev);

// ======================= SERIAL DEVICE CLASS =======================

/// @brief Allows interaction over a serial stream in a packet oriented way. Uses the SerialTransfer object from
/// SerialTransfer library (features packetized serial transactions up to payloads of 254 bytes,
/// using of COBS and CRC). This class has better support for callback-based usage and device identification, and aims
/// at slightly improving ease-of-use. 
/// SerialTransfer repository: https://github.com/PowerBroker2/SerialTransfer
class SerialDevice {
private:

    static const int MAX_HANDLERS = 256;  // category IDs are bytes
    PacketHandler handlers[MAX_HANDLERS] = {nullptr};
    WidePacketHandler baseHandler = nullptr;

public:
    SerialTransfer txf;
    char peerName[32] = "";
    char deviceName[32]; // used for authentication with the other device.
    HardwareSerial* ser;
    
    SerialDevice(HardwareSerial& serial, const char* name = "dev_default");
    
    // begins serial communication
    void begin(unsigned long baud);

    // Registers a handler function for a specific packet id
    void on(uint8_t packetId, PacketHandler handler);

    // Registers a fallback handler function for any received packet
    void onAny(WidePacketHandler handler);

    // polls the serial stream and calls the appropriate handler if a full packet has been received
    void poll();

    // Sends an identification request to peer; returns true if peer responded
    bool requestPeername(uint32_t timeoutMs);

    // Blocks execution until a packet is received, returns remaining time until timeout
    uint64_t waitPacket(uint64_t timeoutMs);

    // Parses incoming serial data. Returns amount of payload bytes if successful
    inline uint8_t available();

    // ======================= SEND API =======================

    uint8_t sendBytes(const byte *buffer, size_t size, uint8_t packId = 0);

    template <size_t N>
    uint8_t sendPacket(char (&str)[N], uint8_t packId = 0);

    template <typename T>
    uint8_t sendPacket(const T& obj, uint8_t packId = 0);

    uint8_t sendPacket(const char* str, uint8_t packId = 0);

    // ======================= LARGE TRANSFER PROTOCOL =======================

    auto sendLarge(const byte *buffer, size_t size, uint8_t packId = 0);

    // ======================= RECEIVE API =======================

    template <typename T>
    size_t recvPacket(T& obj);

    size_t recvBytes(byte* dst, size_t cap);

    void recvPacket(char* dst, size_t cap);

    template <size_t N>
    void recvPacket(char (&dst)[N]);

    // clears buffers and resets the device
    void reset();
};
