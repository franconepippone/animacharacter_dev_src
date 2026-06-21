#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include "AccelStepper.h"
#include "FastAccelStepper.h"
#include "FastAccelStepperEngine.h"

#include "env_dep/body/constants.h"
#include "env_dep/body/serdev_handlers.h"
#include "SerialDevice.h"

FastAccelStepperEngine engine;
FastAccelStepper* stepperR = nullptr;
FastAccelStepper* stepperL = nullptr;
AccelStepper stepperROT(AccelStepper::DRIVER, PIN_STP_ROT_STEP, PIN_STP_ROT_DIR);

int32_t stepperR_trgt = 0;
int32_t stepperL_trgt = 0;

/// @brief Initializes stepper motors objects
int8_t initializeHardware() {
    _debug_blink_builtin(3, 100);
    engine.init();
    stepperL = engine.stepperConnectToPin(PIN_STP_L_STEP);
    stepperL->setEnablePin(PIN_STP_L_EN);
    stepperL->setDirectionPin(PIN_STP_L_DIR);
    stepperL->setSpeedInHz(MAX_SPEED_STPS); // max velocity
    stepperL->setAcceleration(ACCEL_STPSS); // NOTE: THIS CAUSES FATAL HANGS IF STEP PINS ARE INVALID
    
    stepperR = engine.stepperConnectToPin(PIN_STP_R_STEP);
    stepperR->setEnablePin(PIN_STP_R_EN);
    stepperR->setDirectionPin(PIN_STP_R_DIR);
    stepperR->setSpeedInHz(MAX_SPEED_STPS); // max velocity
    stepperR->setAcceleration(ACCEL_STPSS); // NOTE: THIS CAUSES FATAL HANGS IF STEP PINS ARE INVALID
    
    stepperROT.setMaxSpeed(MAX_SPEED_ROT);
    stepperROT.setAcceleration(ACCEL_ROT);
    
    // Turns the drivers ON
    pinMode(PIN_STP_ROT_EN, OUTPUT);
    digitalWrite(PIN_STP_ROT_EN, LOW);
    stepperR->enableOutputs();
    stepperL->enableOutputs();

    stepperL->moveTo(0);
    stepperR->moveTo(0);
    
    _debug_blink_builtin(10, 50);
    return 0;
}

/// @brief  Deinitializes stepper motors - turns all drivers off
void deinitializeHardware() {
    pinMode(PIN_STP_ROT_EN, OUTPUT);
    pinMode(PIN_STP_L_EN, OUTPUT);
    pinMode(PIN_STP_R_EN, OUTPUT);

    // Force turns all the pins off
    digitalWrite(PIN_STP_ROT_EN, HIGH);
    digitalWrite(PIN_STP_L_EN, HIGH); 
    digitalWrite(PIN_STP_R_EN, HIGH);
    
    // if already bound to valid objects, call these as well
    if (stepperL) stepperL->disableOutputs();
    if (stepperR) stepperR->disableOutputs();

}

void driveHardare() {
    // we only update positions if they have actually changed
    if (bodyMotionVars.stp_r != stepperR_trgt) {
        stepperR_trgt = bodyMotionVars.stp_r;
        stepperR->moveTo(bodyMotionVars.stp_r);
    }
    if (bodyMotionVars.stp_r != stepperL_trgt) {
        stepperL_trgt = bodyMotionVars.stp_l;
        stepperL->moveTo(bodyMotionVars.stp_l);
    }
    if (bodyMotionVars.mot_rot != stepperROT.targetPosition()) 
        stepperROT.moveTo(bodyMotionVars.mot_rot);
    
    // drive steppers (only the accell stepper one, others are timer-based)
    stepperROT.run();
}