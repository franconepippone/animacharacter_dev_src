#include <Arduino.h>
#include "SerialDevice.h"
#include "build_info.h"
#include <Hashtable.h>
#include <timer/Timer.h>

// for some reasons on these architectures min and max are renamed _min and _max, so we just redefine them here
#if defined(ESP8266) || defined(ESP32)
    #define min(a,b) ((a) < (b) ? (a) : (b))
    #define max(a,b) ((a) > (b) ? (a) : (b))
#endif

#if defined(ESP8266) || defined(ESP32)
  #define LED_ON  LOW
  #define LED_OFF HIGH
#else
  #define LED_ON  HIGH
  #define LED_OFF LOW
#endif

// This is only defined on esp8266
#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif


//#define IGNORE_SERIAL_DEVICE_DEBUG_CODE

// you can define IGNORE_SERIAL_DEVICE_DEBUG_CODE to completely remove debug code, slithly lighter binary
// =====defined================== DEBUG FUNCTIONS =======================

void _debug_blink_builtin(int times, int period) {
    pinMode(LED_BUILTIN, OUTPUT);
    for (int i = 0; i < times; i++) {
        digitalWrite(LED_BUILTIN, LED_ON);
        delay(period);
        digitalWrite(LED_BUILTIN, LED_OFF);
        delay(period);
    }
    digitalWrite(LED_BUILTIN, LED_OFF);
}


#ifndef IGNORE_SERIAL_DEVICE_DEBUG_CODE

bool _debug_triggerIdent(SerialDevice* dev) {
    _debug_blink_builtin(20, 20);
    dev->requestPeername(1000);
    _debug_blink_builtin(5, 200);
    dev->sendPacket(dev->peerName);
    delay(200);
    _debug_blink_builtin(20, 20);
    delay(100);
    return false;
}

void _debug_onLargeRx(SerialDevice* dev, byte* buff, uint32_t size, uint8_t packId) {
    _debug_blink_builtin(packId, 200);
    dev->sendBytes(buff, min(255, size), packId);
} 

bool _debug_triggerLargeTx(SerialDevice* dev) {
    delay(100);
    _debug_blink_builtin(20, 20);
    delay(100);
    static const char text[] = "Hi from large transfer!";
    //static const char text[] = "ad";

    dev->sendLarge((byte*)text, sizeof(text), 5, 500, 3);
    delay(1000);
    _debug_blink_builtin(20, 20);
    delay(100);
    return false;
}

#endif

// ======================== DEFAULT CALLBACKS ========================

bool _handleAuthRqst(SerialDevice* dev) {
    dev->recvPacket(dev->peerName); // stores name string in the peerName variable 
    dev->sendPacket(dev->deviceName, PACKID_IDENT_RESP);
    return false;
}

bool _handlePing(SerialDevice* dev) {
    // if respond flag is set to true, this is a ping request and we send a response
    bool respond;
    dev->recvPacket(respond);
    if (respond) dev->sendPacket(false, PACKID_PING);
    return false;
}

bool _handleInfoRqst(SerialDevice* dev) {
    // NOTE that this may cause stack overflow
    static char jsonInfoBuff[sizeof(BUILD_INFO_JSON)];
    getBuildInfoJson(jsonInfoBuff, sizeof(BUILD_INFO_JSON));
    dev->sendLarge((byte*)jsonInfoBuff, sizeof(jsonInfoBuff), PACKID_DEV_INFO_RESP);
    return false;
}

// ======= FOR LARGE SERIAL TRANSFER RX ========

bool _handleLargeTxBegin(SerialDevice* dev) {
    /*
    This is the packet used by the peer device to initate a large transfer
    from him to us. We are expecting the payload to be a unit32 representing
    the total size of the large payload to be sent.
    We respond with a single byte packet: 1 = ok to receive, 0 = cannot receive
    */

    // guards against invalid states and reset state if timer has timed out
    if (dev->largeRxCtx.timer.timedOut()) dev->largeRxCtx.state = LargeRxState::READY;
    if (dev->largeRxCtx.state != LargeRxState::READY) return false;

    // reads size of incoming transfer
    uint32_t size = UINT32_MAX;
    dev->recvPacket(size);
    dev->largeRxCtx.ExpectedSize = size;

    // checks if buffer is bound and large enough
    if (!dev->largeRxCtx.RxBuff || dev->largeRxCtx.RxBuffSize < size) {
        // send negative response
        dev->sendPacket((uint8_t)0, PACKID_LARGETX_BEGIN_RESP);
        return false;
    }
    // prepares internal state for receiving
    dev->largeRxCtx.state = LargeRxState::RECVING;
    // send positive response
    dev->sendPacket((uint8_t)1, PACKID_LARGETX_BEGIN_RESP);
    dev->largeRxCtx.timer.start(); // start timeout timer
    return false;
}

bool _handleLargeTxChunk(SerialDevice* dev) {
    /*
    This handler is called when a chunk of a large transfer is received.
    The payload contains the chunk data.
    We need to copy it into the bound buffer at the correct offset,
    and send an ack packet back to the sender.
    */

    // too much time as passed since last chunk, transfer invalidated
    if (dev->largeRxCtx.timer.timedOut()) dev->largeRxCtx.state = LargeRxState::READY;
    if (dev->largeRxCtx.state != LargeRxState::RECVING) return false;

    uint32_t offset = 0;
    dev->recvPacket(offset); // first read offset
    offset = min(offset, dev->largeRxCtx.RxBuffSize); // makes sure offset is not out of bounds

    // subtract 4 bytes used by offset itself
    uint32_t chunkSize = dev->txf.packet.bytesRead - 4;
    // clamp chunk size if offset + chunkSize exceeds buffer size
    if (dev->largeRxCtx.RxBuff) {
        // this can be at min 0
        chunkSize = min(chunkSize, (uint32_t)(dev->largeRxCtx.RxBuffSize - offset));
    } else {
        // transfer is invalid, no valid buffer
        dev->largeRxCtx.timer.fire();
        dev->largeRxCtx.state = LargeRxState::READY;
        return false;
    }
    // this is guarded by the previous check, so we don't write into invaid memory
    //dev->recvBytes(dev->largeRxCtx.RxBuff + offset, chunkSize); // WE 
    memcpy(dev->largeRxCtx.RxBuff + offset, dev->txf.packet.rxBuff + 4, chunkSize);

    // send ack with attached chunk size (not used for now)
    dev->sendPacket(chunkSize, PACKID_LARGETX_ACK);
    
    // restart timeout timer
    dev->largeRxCtx.timer.start();
    return false;
}

bool _handleLargeTxEnd(SerialDevice* dev) {
    /*
    This handler is called when the sender indicates the end of a large transfer,
    it resets the internal state and calls the user handler if assigned.
    */

    // too much time as passed since last chunk, transfer invalidated
    if (dev->largeRxCtx.timer.timedOut()) dev->largeRxCtx.state = LargeRxState::READY;
    if (dev->largeRxCtx.state != LargeRxState::RECVING) return false;

    uint8_t packId = PACKID_INVALID_PACKET;
    dev->recvPacket(packId); // original packet id

    if (dev->largeRxCtx.RecvHandler) {
        // call user handler for large transfers
        dev->largeRxCtx.RecvHandler(dev, dev->largeRxCtx.RxBuff, dev->largeRxCtx.ExpectedSize, packId);
    }
    // reset state
    dev->largeRxCtx.timer.fire();
    dev->largeRxCtx.state = LargeRxState::READY;
    return false;
}

// ======================= SERIAL DEVICE IMPLEMENTATION =======================

SerialDevice::SerialDevice(HardwareSerial& serial, const char* name)
    : ser(&serial)
{
    strncpy(deviceName, name, sizeof(deviceName));
    // assigns internal callbacks
    on(PACKID_IDENT_RQST, _handleAuthRqst);
    on(PACKID_PING, _handlePing);
    on(PACKID_DEV_INFO_RQST, _handleInfoRqst);
    on(PACKID_LARGETX_BEGIN, _handleLargeTxBegin);
    on(PACKID_LARGETX_CHUNK, _handleLargeTxChunk);
    on(PACKID_LARGETX_END, _handleLargeTxEnd);
    txf.begin(*ser);

    #ifndef IGNORE_SERIAL_DEVICE_DEBUG_CODE
    // assign debug triggers callbacks
    on(PACKID_DEBUG_TRIGGER_IDENT_RQST, _debug_triggerIdent);
    on(PACKID_DEBUG_TRIGGER_LARGE_TX, _debug_triggerLargeTx);
    // assign debug large rx handler (this is ment to be overwritten by user)
    onLargeRecv(_debug_onLargeRx);
    #endif
}

void SerialDevice::begin(unsigned long baud) {
    ser->begin(baud);
}

void SerialDevice::on(uint8_t packetId, PacketHandler handler) {
    if (packetId <= MAX_PACK_ID) {
        handlersTable.put(packetId, handler);
    }
}

void SerialDevice::onAny(WidePacketHandler handler) {
    baseHandler = handler;
}

void SerialDevice::onLargeRecv(LargePacketHandler handler) {
    largeRxCtx.RecvHandler = handler;
}

void SerialDevice::configLargeRx(byte* buffer, uint32_t maxSize) {
    largeRxCtx.RxBuff = buffer;
    largeRxCtx.RxBuffSize = maxSize;
}

uint8_t SerialDevice::poll() {
    uint8_t amount = available();
    if (amount) {
        const uint8_t latestPackId = txf.currentPacketID();
        PacketHandler *hndlr = handlersTable.get(latestPackId);
        if (hndlr) {
            (*hndlr)(this);
            return 0;
        } else if (baseHandler) {
            baseHandler(latestPackId, this);
            return 0;
        } else return amount;
    }
    return 0;
}

uint8_t SerialDevice::available() {
    return txf.available();
}

bool SerialDevice::requestPeername(uint32_t timeoutMs) {
    sendPacket(deviceName, PACKID_IDENT_RQST);

    auto remaining = waitPacketOfId(PACKID_IDENT_RESP, timeoutMs);
    if (!remaining) return false;
    recvPacket(peerName); 
    return true;
}

uint64_t SerialDevice::waitPacketOfId(uint8_t packId, uint64_t timeoutMs) {
    while (1) {
        timeoutMs = waitPacket(timeoutMs);
        if (!timeoutMs) return 0;

        const uint8_t id = txf.currentPacketID();
        if (packId == id) {
            return timeoutMs;
        }
    }
}

uint64_t SerialDevice::waitPacket(uint64_t timeoutMs) {
    auto start = millis();
    uint64_t remaining = timeoutMs;
    while (remaining) {
        auto elapsed = millis() - start;
        remaining = max((uint64_t)0, timeoutMs - elapsed);
        if (available()) return remaining;
    }
    return 0;
}

// ======================= TX + SEND API (inspired to original library) =======================

// clear the tx buffer (just resets the internal pointer)
inline void SerialDevice::clearTxBuff() {
    txBuffNextIdx = 0;
}

// appends object bytes in the tx buffer (returns 0 and fails if buffer overflow)
// returns next index (always non-zero) if ok
template <typename T>
uint8_t SerialDevice::txObj(T& obj, const uint16_t &len) {
    if (len + txBuffNextIdx > sizeof(txf.packet.txBuff)) return 0; //overflow
    
    txBuffNextIdx = txf.txObj(obj, txBuffNextIdx, len);
    return txBuffNextIdx; 
}

// appends bytes in the tx buffer
uint8_t SerialDevice::txBytes(byte* buff, size_t size) {
    if (size + txBuffNextIdx > sizeof(txf.packet.txBuff)) return 0; //overflow
    
    memcpy(txf.packet.txBuff + txBuffNextIdx, buff, size);
    txBuffNextIdx += size;
    return txBuffNextIdx;
}

// sends all bytes in the tx buffer, and clears the buffer
uint8_t SerialDevice::send(uint8_t packId) {
    auto tmp = txf.sendData(txBuffNextIdx, packId);
    clearTxBuff();
    return tmp;
}

// ======================= SEND API =======================

uint8_t SerialDevice::sendBytes(const byte *buffer, size_t size, uint8_t packId) {
    size = min(size, sizeof(txf.packet.txBuff));
    memcpy(txf.packet.txBuff, buffer, size);
    return txf.sendData(size, packId);
}

template <size_t N>
uint8_t SerialDevice::sendPacket(char (&str)[N], uint8_t packId) {
    size_t len = strnlen(str, N);
    return sendBytes((byte*)str, len, packId);
}

template <typename T>
uint8_t SerialDevice::sendPacket(const T& obj, uint8_t packId) {
    uint16_t size = txf.txObj(obj);
    return txf.sendData(size, packId);
}

uint8_t SerialDevice::sendPacket(const char* str, uint8_t packId) {
    uint16_t size = strnlen(str, 254);
    return sendBytes((byte*)str, size, packId);
}

// ======================= LARGE TRANSFER =======================
 

uint32_t SerialDevice::sendLarge(byte *buffer, uint32_t size, uint8_t packId, uint32_t timeoutMs, uint8_t chunkSize) 
{
    sendPacket(size, PACKID_LARGETX_BEGIN);
    //sendBytes((byte*)&size, sizeof(size), PACKID_LARGETX_BEGIN);

    auto rmning = waitPacketOfId(PACKID_LARGETX_BEGIN_RESP, timeoutMs);
    if (!rmning) return 0;  // if response times out

    bool transfOk; // if peer has agreed to the transfer 
    recvPacket(transfOk);
    if (!transfOk) return 0;

    uint32_t offset = 0;
    uint32_t actualChunkSize = 0;
    while (offset < size)
    {
        actualChunkSize = min((uint32_t)chunkSize, size - offset);
        clearTxBuff(); // make sure tx buffer is clear

        for (int i = 0; i < LARGE_TRANSFER_SEND_RETRY_AMOUNT; i++) {
            // fills the tx buffer
            txObj(offset);
            txBytes(buffer + offset, actualChunkSize);
            send(PACKID_LARGETX_CHUNK); // sends all data in tx buff

            rmning = waitPacketOfId(PACKID_LARGETX_ACK, timeoutMs);
            if (rmning) break;
        }
        if (!rmning) return 0;  // if remaining is zero (timeout expired), transfer failed.
        offset += actualChunkSize;
    }

    sendPacket(packId, PACKID_LARGETX_END);
    return offset + actualChunkSize;
}


// ======================= RECEIVE API =======================

template <typename T>
size_t SerialDevice::recvPacket(T& obj) {
    return txf.rxObj(obj);
}

size_t SerialDevice::recvBytes(byte* dst, size_t cap) {
    size_t n = min(cap, (size_t)txf.bytesRead);
    memcpy(dst, txf.packet.rxBuff, n);
    return n;
}

size_t SerialDevice::recvPacket(char* dst, size_t cap) {
    if (!dst || !cap) return 0;

    size_t n = strnlen((char*)txf.packet.rxBuff, txf.bytesRead);
    if (n >= cap) n = cap - 1;

    memcpy(dst, txf.packet.rxBuff, n);
    dst[n] = '\0';
    return n;
}

template <size_t N>
size_t SerialDevice::recvPacket(char (&dst)[N]) {
    size_t n = strnlen((char*)txf.packet.rxBuff, txf.bytesRead);
    if (n >= N) n = N - 1;

    memcpy(dst, txf.packet.rxBuff, n);
    dst[n] = '\0';
    return n;
}

// ======================= RESET =======================

void SerialDevice::reset() {
    txf.reset();
}
