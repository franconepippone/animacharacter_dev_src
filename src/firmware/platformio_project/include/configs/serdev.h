#pragma once
#include <Arduino.h>

// These is the base configuration shared across all the devices.
// These protocol rules should be also followed by the commander devices (tipically python SerialDevice-based drivers)

#define PSP_BAUD_RATE 115200

// PSP custom packet categories bytes (from 0x11 to 0xff)   
#define PSP_PACKID_MOTION 1
#define PSP_PACKID_LEDS 2
#define PSP_PACKID_PARAMETERS 3
#define PSP_PACKID_CONTROL_FLAGS 4 // hardware related (start, stop, reset)
#define PSP_PACKID_DIAGNOSTICS 5

// PSP custom diagnostic error codes (from 11 to 255)
#define PSP_ERRCODE_HARDWARE_INIT_FAIL 0x11 // error during hardware initialization

// lifecycle request flags bits
#define INIT_HARDWARE 1
#define DEINIT_HARDWARE 2
#define BEGIN_ALL 4

// only returns true if bit specified by mask is 1, then sets it to 0
inline bool checkAndClearBit(byte &c, byte mask) {
    return (c & mask) ? (c &= ~mask), true : false;
}

struct ControlFlags {
    byte flags = 0; // flags byte

    inline bool init_hw_rqst() {return checkAndClearBit(flags, INIT_HARDWARE);}
    inline bool begin_all_rqst() {return checkAndClearBit(flags, BEGIN_ALL);}
    inline bool deinit_hw_rqst() {return checkAndClearBit(flags, DEINIT_HARDWARE);}

} __attribute__((packed));

