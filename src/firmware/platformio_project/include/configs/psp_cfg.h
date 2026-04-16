
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
