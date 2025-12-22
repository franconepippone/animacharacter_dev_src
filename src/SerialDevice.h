#pragma once
#include <Arduino.h>
#include "SerialTransfer.h"

// ======================= CONSTANTS / TYPEDEFS =======================

class SerialDevice;

typedef bool (*PacketHandler)(SerialDevice*);
typedef bool (*WidePacketHandler)(uint8_t, SerialDevice*);
typedef void (*LargePacketHandler)(byte *buffer, size_t size, uint8_t packId);

#define LARGE_TRANSFER_CHUNK_SIZE 20
#define LARGE_TRANSFER_SEND_RETRY_AMOUNT 5

// ======================= DEFAULT PACKET IDs =======================

// default packets IDs (reserved 200-220)
#define PACKID_IDENT_RQST 200
#define PACKID_IDENT_RESP 201
#define PACKID_DIAGNOSTIC 202
#define PACKID_PING 203
// packets for large transfer
#define PACKID_LARGETX_BEGIN 204
#define PACKID_LARGETX_CHUNK 205
#define PACKID_LARGETX_BEGIN_RESP 206
#define PACKID_LARGETX_ACK 207
#define PACKID_LARGETX_END 208

// debug hooks
#define PACKID_DEBUG_TRIGGER_IDENT_RQST 210
#define PACKID_DEBUG_TRIGGER_LARGE_TX 211

/*  THESE FUNCTIONS ARE INTERNAL AND NOT NEEDED IN THIS FILE, WHY PUT THEM HERE AT ALL?
// ======================= DEBUG FUNCTIONS =======================

// Blinks the built-in LED a number of times
void _debug_blink_builtin(int times, int period = 100);

// used to trigger device to perform a peername request (used for debugging)
bool _debug_triggerIdent(SerialDevice* dev);

// ======================= DEFAULT PACK HANDLERS =======================
// Handler for ping
bool _handlePing(SerialDevice* dev);

// Handler for device identification protocol
bool handleAuthRqst(SerialDevice* dev);
*/

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
    LargePacketHandler largeRecvHandler = nullptr;
    byte* largeRxBuff = nullptr;
    uint32_t largeRxBuffSize = 0;
    size_t txBuffNextIdx = 0;   // used with txObj, txBytes, send (keeps track of objects in tx buff)

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

    // Registers a handler function for any received packet from Large Transfers
    void onLargeRecv(LargePacketHandler handler);
    
    // Assigns a buffer to store packets received from Large Transfers (required for LT to work)
    void bindLargeRxBuff(byte* buffer, uint32_t maxSize);

    // polls the serial stream and calls the appropriate handler if a full packet has been received.
    // If no handler was called, returns the amount of payload bytes in the buffer.
    uint8_t poll();

    // Sends an identification request to peer; returns true if peer responded
    bool requestPeername(uint32_t timeoutMs);

    // Blocks execution until a packet is received, returns remaining time until timeout
    uint64_t waitPacket(uint64_t timeoutMs);

    // Similar to wait packet, excepts it waits for a packet of specific id (ignores all other packets)
    uint64_t waitPacketOfId(uint8_t packId, uint64_t timeoutMs);

    // Parses incoming serial data. Returns amount of payload bytes if successful
    // NOTE: This bypasses handlers! Use this if you want to process packets manually,
    // otherwise, use poll()
    inline uint8_t available();

    // ======================= TX + SEND API (inspired to original library) =======================

    // clear the tx buffer (just resets the internal pointer)
    void clearTxBuff();

    // appends object bytes in the tx buffer
    template <typename T>
    uint8_t txObj(T& obj, const uint16_t &len = sizeof(T));

    // copies and appends bytes in the tx buffer
    uint8_t txBytes(byte* buff, size_t len);

    // sends all bytes in the tx buffer, and clears the buffer
    uint8_t send(uint8_t packId = 0);

    // ======================= SEND API =======================

    uint8_t sendBytes(const byte *buffer, size_t size, uint8_t packId = 0);

    template <size_t N>
    uint8_t sendPacket(char (&str)[N], uint8_t packId = 0);

    template <typename T>
    uint8_t sendPacket(const T& obj, uint8_t packId = 0);

    uint8_t sendPacket(const char* str, uint8_t packId = 0);

    // ======================= LARGE TRANSFER PROTOCOL =======================

    size_t sendLarge(byte *buffer, size_t size, uint8_t packId = 0, uint32_t timeoutMs = 500);

    // ======================= RECEIVE API =======================

    template <typename T>
    // recv arbitrary object from rx buffer
    size_t recvPacket(T& obj);

    // recv bytes from rx buffer
    size_t recvBytes(byte* dst, size_t cap);

    size_t recvPacket(char* dst, size_t cap);

    template <size_t N>
    size_t recvPacket(char (&dst)[N]);

    // clears buffers and resets the device
    void reset();
};
