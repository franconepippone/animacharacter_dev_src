#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_PWMServoDriver.h>
#include "esp_system.h"
#include <SerialDevice.h>

#include "utility/vectors.h"
#include "utility/loop_clock.h"
#include "utility/controllers/differential_actuator.h"
#include "utility/controllers/simmetric_pwm_pair.h"

#include "hardware/pwm_devices.h"
#include "hardware/led_driver.h"

#include "app/constants.h"
#include "app/head_controllers.h"
#include "app/psp_configs.h"
#include "app/hardware_interfacing.h"


Clock loopclock; //helper object to ensure consistent looping frequency
packetizedSerial pspdev(Serial, PSP_DEVICE_NAME); // psp device object


void setup() {
    // binds all custom packet handlers and begins serial communication
    setupAndStartPSPDevice(pspdev);

    // hang until initialization request is made
    while (!controlFlags.init_hw_rqst()) {pspdev.poll(); delay(10);}

    int errcode = initializeHardware();
    if (errcode != 0) {
        // notify commander of error during hardware initialization
        pspdev.send_packet(PSPPACKID_DIAGNOSTIC, PSP_ERR_HARDWARE_INIT_FAIL);
        delay(1000);
        esp_restart(); // restarts
    }

    // hang until start request is made
    while (!controlFlags.begin_all_rqst()) {pspdev.poll(); delay(10);}

    // da levare!!!!!!!!!!!!!!!!!!!!
    SERVO_NECK_RIGHT.set_lerp(.05); 
    SERVO_NECK_LEFT.set_lerp(.05); 
    SERVO_MOUTH_LEFT.set_lerp(.05); 
}


void loop() {
    pspdev.poll(); // receives commands and executes handlers
    updateHardare(); // drives hardware with the latest received commands

    if (controlFlags.deinit_hw_rqst()) {
        deinitializeHardware();
        esp_restart();; // software reset TO BE TESTED!!!!!!!!!!!!!!!!!!!!!!!!!!!
    }
    
    uint32_t deltatime = loopclock.tick_ms(10); //ensures a refresh rate of 100Hz (period: 10ms)
    //Serial.println(deltatime);
}