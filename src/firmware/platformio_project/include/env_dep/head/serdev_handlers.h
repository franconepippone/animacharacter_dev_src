#pragma once
#include <Arduino.h>
#include <SerialDevice.h>

#include "configs/psp_cfg.h" // shared across all devices
#include "constants.h"


// only returns true if bit specified by mask is 1, then sets it to 0
inline bool checkAndClearBit(byte &c, byte mask) {
    return (c & mask) ? (c &= ~mask), true : false;
}

// ------------------ Structs for storing received data from pspdev

// BE MINDFUL OF MEMORY PADDING RULES (packet attribute should fix it)!!!
struct HeadMotionVariables {
    uint8_t mouth;                  // mouthControlPacket
    int8_t ear_l;                    // earsControlPacket
    int8_t ear_r;
    uint8_t eyelid_l_wideness;       // eyeboxControlPacket
    uint8_t eyelid_r_wideness;
    int16_t eye_left;
    int16_t eye_right;
    int16_t eye_tilt;
    int16_t neck_r;               // neckControlPacket
    int16_t neck_l;
} __attribute__((packed)) head_control_vars;

struct HeadControlParameters {
    float lerps[13] = LERP_VALUES_DEFAULT;
}  __attribute__((packed)) head_parameters;

struct HeadEyesLeds {
    uint16_t r;
    uint16_t g;
    uint16_t b;
    uint16_t lightL;
    uint16_t lightR;
    bool has_changed = false;
} __attribute__((packed)) head_leds_vars;

struct ControlFlags {
    byte flags = 0; // flags byte

    inline bool init_hw_rqst() {return checkAndClearBit(flags, INIT_HARDWARE);}
    inline bool begin_all_rqst() {return checkAndClearBit(flags, BEGIN_ALL);}
    inline bool deinit_hw_rqst() {return checkAndClearBit(flags, DEINIT_HARDWARE);}

} controlFlags;



/* --------------- Handlers for received motion control packets (animatronic part/device specific) */

bool handleMotion(SerialDevice* dev) {
    dev->recvPacket(head_control_vars);
    return false;
}

bool handleLeds(SerialDevice* dev) {
    dev->recvPacket(head_leds_vars);
    head_leds_vars.has_changed = true;
    return false;
}

bool handleControl(SerialDevice* dev) {
    byte newFlagByte;
    dev->recvPacket(newFlagByte);
    controlFlags.flags |= newFlagByte;
    return false;
}

// NEEDS TESTING
bool handleParameters(SerialDevice* dev) {
    // Ensure we have enough data
    float lerps[13];
    auto size = dev->recvPacket(lerps);
    if (size < sizeof(float) * 13) return; // safety check

    // Loop through all 13 floats
    for (size_t i = 0; i < 13; i++) {
        float val = lerps[i];
        if (val > 0.0f && val < 1.0f) {  // only copy values strictly in (0,1)
            head_parameters.lerps[i] = val;
        }
        // else: leave the existing value untouched
    }
    return false;
}

// quick setup funtcion to run from main.cpp

int setupAndStartPSPDevice(SerialDevice& pspdev) {
    // Configure pspdev with packet handlers
    pspdev.on(PSPPACKID_MOTION, handleMotion);
    pspdev.on(PSPPACKID_PARAMETERS, handleParameters);
    pspdev.on(PSPPACKID_LEDS, handleLeds);
    pspdev.on(PSPPACKID_CONTROL_FLAGS, handleControl);

    pspdev.begin(PSP_BAUD_RATE);
    return 0;
}