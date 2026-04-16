
// These is the base configuration shared across all the devices

#define PSP_BAUD_RATE 115200
// Device name
#define PSP_DEVICE_NAME "AC01-HEAD"

// PSP custom packet categories bytes (from 0x11 to 0xff)   
#define PSPPACKID_MOTION 1
#define PSPPACKID_LEDS 2
#define PSPPACKID_PARAMETERS 3
#define PSPPACKID_CONTROL_FLAGS 4 // hardware related (start, stop, reset)
#define PSPPACKID_DIAGNOSTICS 5

// PSP custom diagnostic error codes (from 11 to 255)
#define ERRCODE_HARDWARE_INIT_FAIL 0x11 // error during hardware initialization

// lifecycle request flags bits
#define INIT_HARDWARE 1
#define DEINIT_HARDWARE 2
#define BEGIN_ALL 4
