#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include "user_interface.h"

#include <SerialDevice.h>
#include "configs/psp_cfg.h"
#include "utility/loop_clock.h"

#include "env_dep/body/constants.h"
#include "env_dep/body/serdev_handlers.h"
#include "env_dep/body/hardware_interface.h"

#define PSP_DEVICE_NAME "AC01:BODY"

Clock loopclock; //helper object to ensure consistent looping frequency
SerialDevice dev(Serial, PSP_DEVICE_NAME); // psp device object


void setup() {
    // this makes sure drivers are off until commander actually wants to initialize
    deinitializeHardware();
    
    // binds all custom packet handlers and begins serial communication
    setupAndStartPSPDevice(dev);

    // hang until initialization request is made
    while (!controlFlags.init_hw_rqst()) {dev.poll(); delay(10);}

    int errcode = initializeHardware();
    if (errcode != 0) {
        // notify commander of error during hardware initialization
        dev.sendPacket(PSP_PACKID_DIAGNOSTICS, PSP_ERRCODE_HARDWARE_INIT_FAIL);
        delay(1000);
        system_restart(); // restarts
    }

    // hang until start request is made
    while (!controlFlags.begin_all_rqst()) {dev.poll(); delay(10);}
}


void loop() {
    dev.poll(); // receives commands and executes handlers
    driveHardare(); // drives hardware with the latest received commands

    if (controlFlags.deinit_hw_rqst()) {
        deinitializeHardware();
        system_restart(); // software reset TO BE TESTED!!!!!!!!!!!!!!!!!!!!!!!!!!!
    }
    
    uint32_t deltatime = loopclock.tick_ms(10); //ensures a refresh rate of 100Hz (period: 10ms)
    //Serial.println(deltatime);
}