#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>

#include "utility/controllers/simmetric_pwm_pair.h"

#include "hardware/pwm_devices.h"
#include "hardware/drivers.h"

#include "app/constants.h"
#include "app/head_controllers.h"

//creates a piecewise function f(x) = f0 + (x-x0) * [m1 if (x > x0) else m0]
#define InputLambda(x0, fx0, m1, m0) [] (int16_t in) {float s = (in > x0); return (pulse12bit)constrain((fx0 + (float)(in - x0)*(s*m1 + (1-s)*m0)), 0.0, (float)MAX_12BIT_PWM_VALUE);}

#define InputLambdaLinear(m, q) [] (int16_t in) {return get_validPWM12((float)(in)*m + q);}

/* Initialization and calibration of servo objects */
PWMServo<int16_t> SERVO_EYELID_DR(CHANNEL_EYELID_DR, EYELID_DR_PULSE_MIN, EYELID_DR_PULSE_MAX, InputLambda(0, 364, 3.66, 3.1142));
PWMServo<int16_t> SERVO_EYELID_UR(CHANNEL_EYELID_UR, EYELID_UR_PULSE_MIN, EYELID_UR_PULSE_MAX, InputLambda(0, 231, 3.08, 2.35));
PWMServo<int16_t> SERVO_EYELID_DL(CHANNEL_EYELID_DL, EYELID_DL_PULSE_MIN, EYELID_DL_PULSE_MAX, InputLambda(-20, 238, -4.6, -3.95));
PWMServo<int16_t> SERVO_EYELID_UL(CHANNEL_EYELID_UL, EYELID_UL_PULSE_MIN, EYELID_UL_PULSE_MAX, InputLambda(0, 383, -3.12, -2.7));
PWMServo<int16_t> SERVO_EYE_L(CHANNEL_EYE_L, EYE_L_PULSE_MIN, EYE_L_PULSE_MAX, InputLambda(0, 283, 2.035, 2));
PWMServo<int16_t> SERVO_EYE_R(CHANNEL_EYE_R, EYE_R_PULSE_MIN, EYE_R_PULSE_MAX, InputLambda(0, 289, 2.1, 1.95));
PWMServo<int16_t> SERVO_EYE_TILT(CHANNEL_EYE_TILT, EYE_TILT_PULSE_MIN, EYE_TILT_PULSE_MAX, InputLambda(0, 250, -3.63, -3.6));

PWMServo<int16_t> SERVO_EAR_LEFT(CHANNEL_EAR_LEFT, EAR_LEFT_PULSE_MIN, EAR_LEFT_PULSE_MAX, InputLambdaLinear(_EAR_L_INPUT_SLOPE, EAR_LEFT_PULSE_MID));
PWMServo<int16_t> SERVO_EAR_RIGHT(CHANNEL_EAR_RIGHT, EAR_RIGHT_PULSE_MIN, EAR_RIGHT_PULSE_MAX, InputLambdaLinear(_EAR_R_INPUT_SLOPE, EAR_RIGHT_PULSE_MID));
PWMServo<int16_t> SERVO_MOUTH_LEFT(CHANNEL_MOUTH_LEFT, MOUTH_PULSE_MIN, MOUTH_PULSE_MAX);
PWMServo<int16_t> SERVO_MOUTH_RIGHT(CHANNEL_MOUTH_RIGHT, 0, 500); // automatically limited by mouth left

PWMServo<int16_t> SERVO_NECK_RIGHT(CHANNEL_NECK_R, 0, 1000);
PWMServo<int16_t> SERVO_NECK_LEFT(CHANNEL_NECK_L, 0, 1000);

PWMServo<int16_t>* servos[] = {&SERVO_EYELID_DR, &SERVO_EYELID_UR, &SERVO_EYELID_DL, &SERVO_EYELID_UL, &SERVO_EYE_L, &SERVO_EYE_R, &SERVO_EYE_TILT, &SERVO_EAR_LEFT, &SERVO_EAR_RIGHT, &SERVO_MOUTH_LEFT, &SERVO_MOUTH_RIGHT, &SERVO_NECK_RIGHT, &SERVO_NECK_LEFT};
const size_t servo_amount = sizeof(servos) / sizeof(servos[0]);

EyelidsController eyeLeft(&SERVO_EYELID_UL, &SERVO_EYELID_DL);
EyelidsController eyeRight(&SERVO_EYELID_UR, &SERVO_EYELID_DR);

SimmetricPWM12Pair mouth(SERVO_MOUTH_LEFT, SERVO_MOUTH_RIGHT, 280);