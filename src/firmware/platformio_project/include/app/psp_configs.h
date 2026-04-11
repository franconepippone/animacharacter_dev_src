#pragma once
#include <Arduino.h>
#include <SerialDevice.h>


#define PSP_BAUD_RATE 115200
// Device name
#define PSP_DEVICE_NAME "AC01-HEAD"

// PSP custom packet categories bytes (from 0x11 to 0xff)   
#define PSPPACKID_MOTION 0x11
#define PSPPACKID_LEDS 0x12
#define PSPPACKID_PARAMETERS 0x13
#define PSPPACKID_CONTROL_FLAGS 0x14 // hardware related (start, stop, reset)

// PSP custom diagnostic error codes (from 11 to 255)
#define PSP_ERR_HARDWARE_INIT_FAIL 0x11 // error during hardware initialization

// PSP control flags bits
#define PSP_INIT_HARDWARE 1
#define PSP_DEINIT 2
#define PSP_BEGIN_ALL 4


// only returns true if bit specified by mask is 1, then sets it to 0
bool checkAndClearBit(byte &c, byte mask) {
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

    bool init_hw_rqst() {return checkAndClearBit(flags, PSP_INIT_HARDWARE);}
    bool begin_all_rqst() {return checkAndClearBit(flags, PSP_BEGIN_ALL);}
    bool deinit_hw_rqst() {return checkAndClearBit(flags, PSP_DEINIT);}

} controlFlags;



// --------------- Handlers for received (custom / animatronic specific) packets

void handleMotion(BaseSerPacket* pck) {
    head_control_vars = *(headMotionVariables*)(pck->data);
}

void handleLeds(BaseSerPacket* pck) {
    head_leds_vars = *(headEyesLeds*)(pck->data);
    head_leds_vars.has_changed = true;
}

void handleControl(BaseSerPacket* pck) {
    byte new_flags = *(pck->data);
    controlFlags.flags |= new_flags;
}

// NEEDS TESTING
void handleParameters(BaseSerPacket* pck) {
    // Ensure we have enough data
    if (pck->length < sizeof(float) * 13) return; // safety check

    // Cast packet data to float array
    float* incoming = reinterpret_cast<float*>(pck->data);

    // Loop through all 13 floats
    for (size_t i = 0; i < 13; i++) {
        float val = incoming[i];
        if (val > 0.0f && val < 1.0f) {  // only copy values strictly in (0,1)
            head_parameters.lerps[i] = val;
        }
        // else: leave the existing value untouched
    }
}

// quick setup funtcion to run from main.cpp

int setupAndStartPSPDevice(packetizedSerial& pspdev) {
    // Configure pspdev with packet handlers
    pspdev.on(PSPPACKID_MOTION, handleMotion);
    pspdev.on(PSPPACKID_PARAMETERS, handleParameters);
    pspdev.on(PSPPACKID_LEDS, handleLeds);
    pspdev.on(PSPPACKID_CONTROL_FLAGS, handleControl);

    pspdev.begin(PSP_BAUD_RATE);
    return 0;
}




/*
void receiveCommandsFromSerial() {
    /// Processa i comandi da eseguire
    while (commander_device.recv_packet()) {
        BaseSerPacket* pck = commander_device.get_last_packet();
        // in base alla categoria sceglie cosa fare
        switch (pck->category)
        {
        case PSPPACKID_MOTION:
            head_control_vars = *(headMotionVariables*)(pck->data);
            break;
        
        case PSPPACKID_PARAMETERS:
            head_parameters = *(headControlParameters*)(pck->data);
            break;

        case PSPPACKID_LEDS:    
            head_leds_vars = *(headEyesLeds*)(pck->data);
            head_leds_vars.has_changed = true;
            break;  

        case PSPPACKID_CONTROL:{
            byte new_flags = *(pck->data);
            control_flags.flags |= new_flags; // aggiona le flags
            Serial.println(new_flags);
            break;
        }  

        case PSPPACKID_DIAGNOSTIC:
            break;
        
        default:
            ///notifica il commander che un pacchetto sconosciuto è stato ricevuto
            commander_device.send_packet(PSPPACKID_DIAGNOSTIC, PSP_ERR_UNKNOWN_PACKETID);
            break;
        }
    };
}










void receiveCommandsFromSerial() {
    while (Serial.available() > 0) {

        switch (Serial.read())
        {
        case COMM_EYEBOX_UPDATE:
            Serial.readBytes((byte*)&eyebox_vars, sizeof(eyebox_vars));
            break;
        
        case COMM_NECK_MOVEMENT:
            Serial.readBytes((byte*)&neck_vars, sizeof(neck_vars));
            break;

        case COMM_EAR_MOVEMENT:
            Serial.readBytes((byte*)&ears_vars, sizeof(ears_vars));
            break;

        case COMM_MOUTH_MOVEMENT:
            Serial.readBytes((byte*)&mouth_vars, sizeof(mouth_vars));
            break;

        default:
            Serial.println("Received unknown command");
            Serial.flush();
            break;
        }
  }
}*/