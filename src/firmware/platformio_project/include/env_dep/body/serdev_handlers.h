#pragma once
#include <Arduino.h>
#include <SerialDevice.h>

#include "configs/psp_cfg.h" // shared across all devices/environments
#include "constants.h"


// only returns true if bit specified by mask is 1, then sets it to 0
inline bool checkAndClearBit(byte &c, byte mask) {
    return (c & mask) ? (c &= ~mask), true : false;
}

// ------------------ Structs for storing received data from SerialDevice

struct {
    int16_t stp_r = 0;
    int16_t stp_l = 0;           
    int16_t mot_rot = 0;
} __attribute__((packed)) bodyMotionVars;

struct {
    // rotational acceleration (stp/s^2) of the motion controllers
    uint16 acc_r;
    uint16 acc_l;
    uint16 acc_rot;
}  __attribute__((packed)) bodyControlParams;

// THIS IS ALWAYS DUPLICATE
struct {
    byte flags = 0; // flags byte

    inline bool init_hw_rqst() {return checkAndClearBit(flags, INIT_HARDWARE);}
    inline bool begin_all_rqst() {return checkAndClearBit(flags, BEGIN_ALL);}
    inline bool deinit_hw_rqst() {return checkAndClearBit(flags, DEINIT_HARDWARE);}

} controlFlags;



/* --------------- Handlers for received motion control packets (animatronic part/device specific) */

bool handleMotion(SerialDevice* dev) {
    dev->recvPacket(bodyMotionVars);
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
    dev->recvPacket(bodyControlParams);
    return false;
}

// quick setup funtcion to run from main.cpp

int setupAndStartPSPDevice(SerialDevice& pspdev) {
    // Configure pspdev with packet handlers
    pspdev.on(PSP_PACKID_MOTION, handleMotion);
    pspdev.on(PSP_PACKID_PARAMETERS, handleParameters);
    pspdev.on(PSP_PACKID_CONTROL_FLAGS, handleControl);

    pspdev.begin(PSP_BAUD_RATE);
    return 0;
}