#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include "AccelStepper.h"

#include "env_dep/body/constants.h"
#include "env_dep/body/serdev_handlers.h"

AccelStepper stepperR(AccelStepper::DRIVER, PIN_STP_R_STEP, PIN_STP_R_DIR);
AccelStepper stepperL(AccelStepper::DRIVER, PIN_STP_L_STEP, PIN_STP_L_DIR);
AccelStepper stepperROT(AccelStepper::DRIVER, PIN_STP_ROT_STEP, PIN_STP_ROT_DIR);


/// @brief Initializes stepper motors objects
int initializeHardware() {
    pinMode(PIN_STP_ROT_EN, OUTPUT);
    pinMode(PIN_STP_L_EN, OUTPUT);
    pinMode(PIN_STP_R_EN, OUTPUT);

    // Turns the drivers ON
    digitalWrite(PIN_STP_ROT_EN, LOW); 
    digitalWrite(PIN_STP_L_EN, LOW); 
    digitalWrite(PIN_STP_R_EN, LOW); 

    stepperR.setMaxSpeed(1000);
    stepperR.setAcceleration(500);

    stepperL.setMaxSpeed(1000);
    stepperL.setAcceleration(500);
    
    stepperROT.setMaxSpeed(1000);
    stepperROT.setAcceleration(500);
    
    return 0;
}

/// @brief  Deinitializes stepper motors - turns all drivers off
void deinitializeHardware() {
    pinMode(PIN_STP_ROT_EN, OUTPUT);
    pinMode(PIN_STP_L_EN, OUTPUT);
    pinMode(PIN_STP_R_EN, OUTPUT);

    // Turns the drivers OFF
    digitalWrite(PIN_STP_ROT_EN, HIGH);
    digitalWrite(PIN_STP_L_EN, HIGH); 
    digitalWrite(PIN_STP_R_EN, HIGH); 
}

void driveHardare() {
    // we only update positions if they have actually changed
    if (bodyMotionVars.stp_r != stepperR.targetPosition()) 
        stepperR.moveTo(bodyMotionVars.stp_r);
    if (bodyMotionVars.stp_r != stepperL.targetPosition()) 
        stepperL.moveTo(bodyMotionVars.stp_l);
    if (bodyMotionVars.mot_rot != stepperROT.targetPosition()) 
        stepperROT.moveTo(bodyMotionVars.mot_rot);
    
    // drive steppers
    stepperL.run();
    stepperR.run();
    stepperROT.run();
}