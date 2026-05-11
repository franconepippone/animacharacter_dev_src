#pragma once
#include <Arduino.h>

// These is the base configuration shared across all the devices.
// These protocol rules should be also followed by the commander devices (tipically python SerialDevice-based drivers)

#define PSP_BAUD_RATE 115200

// SerialDevice packet ids (0-199, 231-255)   
#define PSP_PACKID_MOTION 1
#define PSP_PACKID_LEDS 2
#define PSP_PACKID_PARAMETERS 3
#define PSP_PACKID_CONTROL_FLAGS 4 // hardware related (start, stop, reset)
#define PSP_PACKID_DIAGNOSTICS 5

// custom diagnostic error codes (1 byte)
#define DGN_ERR_HARDWARE_INIT_FAIL (uint8_t)0x00 // error during hardware initialization
#define DGN_HARDWARE_INIT_OK (uint8_t)0x01
#define DGN_BEGINALL_OK (uint8_t)0x02
#define DGN_HARDWARE_DEINIT_ACK (uint8_t)0x03

// ----- Body only
#define DGN_WRN_MOTOR_R (uint8_t)0x04
#define DGN_WRN_MOTOR_L (uint8_t)0x05

// lifecycle request flag bitmasks
#define INIT_HARDWARE (byte)0x01
#define BEGIN_ALL (byte)0x02
#define DEINIT_HARDWARE (byte)0x04

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

