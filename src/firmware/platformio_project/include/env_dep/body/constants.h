#pragma once

// Stepper motor pin mapping

// Body tilt right stepper
#define PIN_STP_R_EN 2         //enable driver
#define PIN_STP_R_DIR 3        // direction
#define PIN_STP_R_STEP 9       // step
#define PIN_STP_R_WRN 4        // wrn (when motor s)

// Body left tilt stepper
#define PIN_STP_L_EN 5         //enable driver
#define PIN_STP_L_DIR 6        // direction
#define PIN_STP_L_STEP 10       // step
#define PIN_STP_L_WRN 7        // wrn (when motor s)

// Body rotation stepper
#define PIN_STP_ROT_EN 1         
#define PIN_STP_ROT_DIR 2        
#define PIN_STP_ROT_STEP 3     
// this is a open loop stepper, does not have a WRN