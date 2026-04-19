#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
//#include "user_interface.h"

#include <SerialDevice.h>
#include "utility/loop_clock.h"
#include "configs/serdev.h"

#include "env_dep/body/constants.h"
#include "env_dep/body/serdev_handlers.h"
#include "env_dep/body/hardware_interface.h"
/*
*/
#define PSP_DEVICE_NAME "AC01:BODY"

Clock loopclock; //helper object to ensure consistent looping frequency
SerialDevice dev(Serial, PSP_DEVICE_NAME); // psp device object

int freeRam() {
    extern int __heap_start, *__brkval;
    int v;
    return (int)&v - (__brkval == 0 ? (int)&__heap_start : (int)__brkval);
}


bool onFreeRam(SerialDevice* dev) {
    uint32_t val = freeRam();
    dev->sendPacket(val, 1);
    return false;
}

void setup()
{
  dev.begin(115200);
  dev.on(1, onFreeRam);
  delay(200);

  //_debug_blink_builtin(3, 100);
  //led.blink(500, 800);
  // binds cb
  //dev.configLargeRx(largeRxBuffer, sizeof(largeRxBuffer));
}


void loop()
{
  dev.poll();
  //led.loop();
}

/*

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
        //system_restart(); // restarts
    }

    // hang until start request is made
    while (!controlFlags.begin_all_rqst()) {dev.poll(); delay(10);}
}


void loop() {
    dev.poll(); // receives commands and executes handlers
    driveHardare(); // drives hardware with the latest received commands

    if (controlFlags.deinit_hw_rqst()) {
        deinitializeHardware();
        //system_restart(); // software reset TO BE TESTED!!!!!!!!!!!!!!!!!!!!!!!!!!!
    }
    
    loopclock.tick_ms(10); //ensures a refresh rate of 100Hz (period: 10ms)
    //Serial.println(deltatime);
}

*/