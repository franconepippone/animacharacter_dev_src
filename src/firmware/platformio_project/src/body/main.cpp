#include <Arduino.h>
#include <avr/wdt.h>
#include <Wire.h>
#include <SPI.h>
//#include "user_interface.h"

#include <SerialDevice.h>
#include <timer.h> 
#include "utility/loop_clock.h"
#include "configs/serdev.h"

#include "env_dep/body/constants.h"
#include "env_dep/body/serdev_handlers.h"
#include "env_dep/body/hardware_interface.h"

#define PSP_DEVICE_NAME "AC01:BODY"


void systemRestart() {
    wdt_enable(WDTO_15MS); // shortest timeout
    while (1) {}           // wait for watchdog reset
}


/*
NOTE!! we changed max packet size from 256 to 128 due to RAM constraints!!
*/ 
SerialDevice dev(Serial, PSP_DEVICE_NAME); // psp device object
Timer looptimer(1000);


void setup() {
    // this makes sure drivers are off until commander actually wants to initialize
    deinitializeHardware();
    pinMode(LED_BUILTIN, OUTPUT);
    // binds all custom packet handlers and begins serial communication
    setupAndStartPSPDevice(dev);

    // hang until initialization request is made
    while (!controlFlags.init_hw_rqst()) {dev.poll();}

    int8_t errcode = initializeHardware();
    if (errcode != 0) {
        // notify commander of error during hardware initialization
        dev.sendPacket(DGN_ERR_HARDWARE_INIT_FAIL, PSP_PACKID_DIAGNOSTICS);
        delay(200);
        systemRestart();
    } else {
        dev.sendPacket(DGN_HARDWARE_INIT_OK, PSP_PACKID_DIAGNOSTICS);
    }

    // hang until start request is made
    while (!controlFlags.begin_all_rqst()) {dev.poll(); delay(10);}
    dev.sendPacket(DGN_BEGINALL_OK, PSP_PACKID_DIAGNOSTICS);
    _debug_blink_builtin(10, 60);
}


void loop() {
    dev.poll(); // receives commands and executes handlers
    driveHardare(); // drives hardware with the latest received commands

    if (controlFlags.deinit_hw_rqst()) {
        deinitializeHardware();
        dev.sendPacket(DGN_HARDWARE_DEINIT_ACK, PSP_PACKID_DIAGNOSTICS); // ack of hardware deinit
        delay(200);
        systemRestart();
    }
    
    while (!looptimer.expired()) {
        dev.poll();
        driveHardare();
    }
}