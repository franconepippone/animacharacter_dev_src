#pragma once

// Stepper motor pin mapping

// Body tilt right stepper
#define PIN_STP_R_EN 2         //enable driver
#define PIN_STP_R_DIR 3        // direction
#define PIN_STP_R_STEP 9       // step
#define PIN_STP_R_WRN 4        // wrn (when motor s)
#define MAX_SPEED_STPS 10000
#define ACCEL_STPSS 6000

// Body left tilt stepper
#define PIN_STP_L_EN 5         //enable driver
#define PIN_STP_L_DIR 6        // direction
#define PIN_STP_L_STEP 10       // step
#define PIN_STP_L_WRN 7        // wrn (when motor s)

// Body rotation stepper
#define PIN_STP_ROT_EN 2         
#define PIN_STP_ROT_DIR 3        
#define PIN_STP_ROT_STEP 4
#define MAX_SPEED_ROT 10000
#define ACCEL_ROT 1000 
// this is a open loop stepper, does not have a WRN