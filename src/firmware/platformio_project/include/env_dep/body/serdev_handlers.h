#pragma once
#include <Arduino.h>
#include <SerialDevice.h>

#include "constants.h"
#include "configs/serdev.h" // shared across all devices/environments

// ------------------ Structs for storing received data from SerialDevice

struct BodyMotionVars {
    int16_t stp_r;
    int16_t stp_l;
    int16_t mot_rot;
} __attribute__((packed));

 BodyMotionVars bodyMotionVars;

struct BodyControlParams {
    // rotational acceleration (stp/s^2) of the motion controllers
    uint16_t acc_r;
    uint16_t acc_l;
    uint16_t acc_rot;
}  __attribute__((packed));

BodyControlParams bodyControlParams;


ControlFlags controlFlags;



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