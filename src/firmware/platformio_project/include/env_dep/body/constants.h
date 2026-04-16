#pragma once

// Stepper motor pin mapping

// Body tilt right stepper
#define PIN_STP_R_EN 1         //enable driver
#define PIN_STP_R_DIR 2        // direction
#define PIN_STP_R_STEP 3       // step
#define PIN_STP_R_WRN 4        // wrn (when motor s)

// Body left tilt stepper
#define PIN_STP_L_EN 1         //enable driver
#define PIN_STP_L_DIR 2        // direction
#define PIN_STP_L_STEP 3       // step
#define PIN_STP_L_WRN 4        // wrn (when motor s)

// Body rotation stepper
#define PIN_STP_ROT_EN 1         
#define PIN_STP_ROT_DIR 2        
#define PIN_STP_ROT_STEP 3     
// this is a open loop stepper, does not have a WRN