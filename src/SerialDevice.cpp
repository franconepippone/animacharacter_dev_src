#include <Arduino.h>
#include "SerialDevice.h"


// ======================= DEBUG FUNCTIONS =======================

void _debug_blink_builtin(int times, int period) {
    for (int i = 0; i < times; i++) {
        digitalWrite(13, HIGH);
        delay(period);
        digitalWrite(13, LOW);
        delay(period);
    }
}

bool _debug_triggerIdent(SerialDevice* dev) {
    _debug_blink_builtin(20, 20);
    dev->requestPeername(1000);
    _debug_blink_builtin(5, 200);
    dev->sendPacket(dev->peerName);
    _debug_blink_builtin(20, 20);
    delay(100);
    return false;
}

bool _debug_onLargeRx(byte* buff, size_t size, uint8_t packId) {
    _debug_blink_builtin(packId, 200);
} 

bool _debug_triggerLargeTx(SerialDevice* dev) {
    delay(100);
    _debug_blink_builtin(20, 20);
    delay(100);
    const int SIZE = 15;
    byte buffer[SIZE];

    for (int i = 0; i < SIZE; i++) {
        buffer[i] = (byte)random(0, 256);  // random byte 0–255
    }
    auto size = dev->sendLarge(buffer, 15, 5);
    delay(1000);
    _debug_blink_builtin(20, 20);
    delay(100);
    return false;
}

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


// ======================= SERIAL DEVICE IMPLEMENTATION =======================

SerialDevice::SerialDevice(HardwareSerial& serial, const char* name)
    : ser(&serial)
{
    strncpy(deviceName, name, sizeof(deviceName));
    // assigns internal callbacks
    on(PACKID_IDENT_RQST, _handleAuthRqst);
    on(PACKID_PING, _handlePing);
    on(PACKID_DEBUG_TRIGGER_IDENT_RQST, _debug_triggerIdent);
    on(PACKID_DEBUG_TRIGGER_LARGE_TX, _debug_triggerLargeTx);
    txf.begin(*ser);
}

void SerialDevice::begin(unsigned long baud) {
    ser->begin(baud);
}

void SerialDevice::on(uint8_t packetId, PacketHandler handler) {
    if (packetId < MAX_HANDLERS) {
        handlers[packetId] = handler;
    }
}

void SerialDevice::onAny(WidePacketHandler handler) {
    baseHandler = handler;
}

void SerialDevice::onLargeRecv(LargePacketHandler handler) {
    largeRecvHandler = handler;
}

void SerialDevice::bindLargeRxBuff(byte* buffer, uint32_t maxSize) {
    largeRxBuff = buffer;
    largeRxBuffSize = maxSize;
}

uint8_t SerialDevice::poll() {
    uint8_t amount = available();
    if (amount) {
        const uint8_t latestPackId = txf.currentPacketID();
        if (handlers[latestPackId]) {
            handlers[latestPackId](this);
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
        remaining = max(0, timeoutMs - elapsed);
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
uint8_t SerialDevice::txObj(T& obj, const uint16_t &len = sizeof(T)) {
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
    uint16_t size = strlen(str);
    return sendBytes((byte*)str, size, packId);
}

// ======================= LARGE TRANSFER =======================
 

size_t SerialDevice::sendLarge(byte *buffer, size_t size, uint8_t packId, uint32_t timeoutMs) {
    //uint32_t numChunks = size / LARGE_TRANSFER_CHUNK_SIZE;
    sendBytes((byte*)&size, sizeof(size), PACKID_LARGETX_BEGIN);

    auto rmning = waitPacketOfId(PACKID_LARGETX_BEGIN_RESP, timeoutMs);
    if (!rmning) return 0;  // if response times out

    bool transfOk; // if peer has agreed to the transfer 
    recvPacket(transfOk);
    if (!transfOk) return 0;

    uint32_t offset = 0;
    size_t chunkSize;
    while (offset < size)
    {
        chunkSize = min(LARGE_TRANSFER_CHUNK_SIZE, size - offset);
        clearTxBuff(); // make sure tx buffer is clear

        for (int i = 0; i < LARGE_TRANSFER_SEND_RETRY_AMOUNT; i++) {
            // fills the tx buffer
            auto idx1 = txObj(offset);
            _debug_blink_builtin(idx1, 200);
            delay(500);
            idx1 = txBytes(buffer + offset, chunkSize);
            _debug_blink_builtin(idx1, 250);
            delay(500);
            send(PACKID_LARGETX_CHUNK); // sends all data in tx buff
            _debug_blink_builtin(idx1, 200);

            rmning = waitPacketOfId(PACKID_LARGETX_ACK, timeoutMs);
            if (rmning) {
                delay(50);
                break;
            }
        }
        if (!rmning) return 0;  // if remaining is zero (timeout expired), transfer failed.
        offset += chunkSize;
    }

    sendPacket(packId, PACKID_LARGETX_END);
    return offset + chunkSize;
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
