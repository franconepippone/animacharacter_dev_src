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

void _debug_triggerIdent(SerialDevice* dev) {
    _debug_blink_builtin(20, 20);
    dev->requestPeername(1000);
    _debug_blink_builtin(5, 200);
    dev->sendPacket(dev->peerName);
    _debug_blink_builtin(20, 20);
    delay(100);
}

// ======================== DEFAULT CALLBACKS ========================

void _handleAuthRqst(SerialDevice* dev) {
    dev->recvPacket(dev->peerName); // stores name string in the peerName variable 
    dev->sendPacket(dev->deviceName, PACKID_IDENT_RESP);
}

void _handlePing(SerialDevice* dev) {
    // if respond flag is set to true, this is a ping request and we send a response
    bool respond;
    dev->recvPacket(respond);
    if (respond) dev->sendPacket(false, PACKID_PING);
}


// ======================= SERIAL DEVICE IMPLEMENTATION =======================

SerialDevice::SerialDevice(HardwareSerial& serial, const char* name)
    : ser(&serial)
{
    strncpy(deviceName, name, sizeof(deviceName));
    on(PACKID_IDENT_RQST, _handleAuthRqst);
    on(PACKID_PING, _handlePing);
    on(PACKID_DEBUG_TRIGGER_IDENT_RQST, _debug_triggerIdent);
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

void SerialDevice::poll() {
    while (available()) {
        const uint8_t latestPackId = txf.currentPacketID();
        if (handlers[latestPackId]) {
            handlers[latestPackId](this);
        } else if (baseHandler) {
            baseHandler(latestPackId, this);
        }
    }
}

bool SerialDevice::requestPeername(uint32_t timeoutMs) {
    sendPacket(deviceName, PACKID_IDENT_RQST);

    while (1) {
        timeoutMs = waitPacket(timeoutMs);
        if (!timeoutMs) return false;

        const uint8_t packId = txf.currentPacketID();
        if (packId == PACKID_IDENT_RESP) {
            recvPacket(peerName);
            return true;
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

inline uint8_t SerialDevice::available() {
    return txf.available();
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

void SerialDevice::recvPacket(char* dst, size_t cap) {
    if (!dst || !cap) return;

    size_t n = strnlen((char*)txf.packet.rxBuff, txf.bytesRead);
    if (n >= cap) n = cap - 1;

    memcpy(dst, txf.packet.rxBuff, n);
    dst[n] = '\0';
}

template <size_t N>
void SerialDevice::recvPacket(char (&dst)[N]) {
    size_t n = strnlen((char*)txf.packet.rxBuff, txf.bytesRead);
    if (n >= N) n = N - 1;

    memcpy(dst, txf.packet.rxBuff, n);
    dst[n] = '\0';
}

// ======================= RESET =======================

void SerialDevice::reset() {
    txf.reset();
}
