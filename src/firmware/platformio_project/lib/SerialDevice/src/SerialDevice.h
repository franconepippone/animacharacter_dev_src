#pragma once
#include <Arduino.h>
#include "SerialTransfer.h"
#include <Hashtable.h>
#include <timer.h>

// ======================= CONSTANTS / TYPEDEFS =======================

void _debug_blink_builtin(int times, int period);

class SerialDevice;

typedef bool (*PacketHandler)(SerialDevice*);
typedef bool (*WidePacketHandler)(uint8_t, SerialDevice*);
typedef void (*LargePacketHandler)(SerialDevice* dev, byte *buffer, uint32_t size, uint8_t packId);

#define LARGERX_CHUNK_TIMEOUT_MS 3000 // large transfer chunks can be received at max 3 seconds apart
#define LARGE_TRANSFER_CHUNK_SIZE 240
#define LARGE_TRANSFER_SEND_RETRY_AMOUNT 5
#define MAX_PACK_ID 255 // 0-255

#define DEVICE_NAME_SIZE 16 // bytes to allocate for serialdevice name

// keep track of large transfer rx state
enum LargeRxState {
    READY = 0,
    RECVING = 1,
};

// return value of any operation on stream
enum StreamOpOutcome {
    OK = 0,
    TIMED_OUT = -1,
    ALREADY_INITIATED = -2,
    NOT_INITIATED = -3,
    REFUSED = -4,
    OFFSET_OUT_OF_BOUNDS = -5
};

// ======================= DEFAULT PACKET IDs (reserved 200-230) =======================

// default packets IDs (reserved 200-219)
#define PACKID_IDENT_RQST 200
#define PACKID_IDENT_RESP 201
#define PACKID_DIAGNOSTIC 202
#define PACKID_PING 203
#define PACKID_DEV_INFO_RQST 209
#define PACKID_DEV_INFO_RESP 210
#define PACKID_INVALID_PACKET 211

// packets for large transfer
#define PACKID_LARGETX_BEGIN 204
#define PACKID_LARGETX_CHUNK 205
#define PACKID_LARGETX_BEGIN_RESP 206
#define PACKID_LARGETX_ACK 207
#define PACKID_LARGETX_END 208

// debug hooks (reserved 220-230)
#define PACKID_DEBUG_TRIGGER_IDENT_RQST 220
#define PACKID_DEBUG_TRIGGER_LARGE_TX 221
#define PACKID_DEBUG_FREERAM 222

// ======================= SERIAL DEVICE CLASS =======================

/// @brief Allows interaction over a serial stream in a packet oriented way. Uses the SerialTransfer object from
/// SerialTransfer library (features packetized serial transactions up to payloads of 254 bytes,
/// using of COBS and CRC). This class has better support for callback-based usage, device identification, and
// large data transfers (automatic fragmentation into packets), aiming at slightly improving ease-of-use. 
/// SerialTransfer repository: https://github.com/PowerBroker2/SerialTransfer
class SerialDevice {
private:
    // forced to use int instead of uint8_t, because there's no builting template specialization in the library
    Hashtable<int, PacketHandler> handlersTable;
    WidePacketHandler baseHandler = nullptr;
    size_t txBuffNextIdx = 0;   // used with txObj, txBytes, send (keeps track of objects in tx buff)
    // attributes for large transfer rx state machine
    
public:
    // consider making this a private struct
    struct {
        Timer timer = Timer(LARGERX_CHUNK_TIMEOUT_MS); // 500ms timeout for large transfer reception
        LargeRxState state = LargeRxState::READY;
        byte* RxBuff = nullptr;
        uint32_t RxBuffSize = 0;
        LargePacketHandler RecvHandler = nullptr;
        uint32_t ExpectedSize = 0;
    } largeRxCtx;

    struct {
        uint32_t buffSize = 0;
        bool initiated = false;
    } streamCtx;

    SerialTransfer txf;
    char peerName[DEVICE_NAME_SIZE] = "";
    char deviceName[DEVICE_NAME_SIZE]; // used for authentication with the other device.
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
    void configLargeRx(byte* buffer, uint32_t maxSize);

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
    uint8_t sendPacket(char (&str)[N], uint8_t packId) {
        size_t len = strnlen(str, N);
        return sendBytes((byte*)str, len, packId);
    }

    template <typename T>
    uint8_t sendPacket(const T& obj, uint8_t packId) {
        uint16_t size = txf.txObj(obj);
        return txf.sendData(size, packId);
    }

    uint8_t sendPacket(const char* str, uint8_t packId = 0);

    // ======================= LARGE TRANSFER PROTOCOL =======================

    // Requests the beginning of a large transfer chunk stream. True on success
    StreamOpOutcome SerialDevice::streamBegin(uint32_t buffSize, uint32_t timeoutMs);

    // Sends a chunk to be stored in the peer's rx buffer at given offset (after streamBegin has been called succesfully)
    StreamOpOutcome SerialDevice::streamChunk(byte *buffer, uint32_t size, uint32_t offset, uint32_t timeoutMs);

    // Ends a large transfer chunk stream. This notifies the peer that the whole payload has been received.
    StreamOpOutcome SerialDevice::streamEnd(uint8_t packId);

    uint32_t sendLarge(byte *buffer, uint32_t size, uint8_t packId = 0, uint32_t timeoutMs = 500, uint8_t chunkSize = LARGE_TRANSFER_CHUNK_SIZE);

    // ======================= RECEIVE API =======================

    template <typename T>
    // recv arbitrary object from rx buffer
    size_t recvPacket(T& obj) {
        return txf.rxObj(obj);
    }

    // recv bytes from rx buffer
    size_t recvBytes(byte* dst, size_t cap);

    size_t recvPacket(char* dst, size_t cap);

    template <size_t N>
    size_t recvPacket(char (&dst)[N]) {
        size_t n = strnlen((char*)txf.packet.rxBuff, txf.bytesRead);
        if (n >= N) n = N - 1;

        memcpy(dst, txf.packet.rxBuff, n);
        dst[n] = '\0';
        return n;
    }

    // clears buffers and resets the device
    void reset();
};
