#pragma once

#define SERVO_FREQ 50 // Analog servos run at ~50 Hz updates

// Servos channel on the pca9685
#define CHANNEL_EYELID_DR  0
#define CHANNEL_EYELID_UR  1
#define CHANNEL_EYE_R       2
#define CHANNEL_EYELID_DL  3
#define CHANNEL_EYELID_UL  4
#define CHANNEL_EYE_L       12 // 5
#define CHANNEL_EYE_TILT    8 // from 6
#define CHANNEL_EAR_LEFT 5 // from 7
#define CHANNEL_EAR_RIGHT 11 // from 8
#define CHANNEL_MOUTH_LEFT 9
#define CHANNEL_MOUTH_RIGHT 10
#define CHANNEL_NECK_R 6 //11
#define CHANNEL_NECK_L 7 //12

// LEDS channels/pins
#define CHANNEL_LED_R 15
#define CHANNEL_LED_G 14
#define CHANNEL_LED_B 13
#define IRIS_L_PIN 18 // esp pin
#define IRIS_R_PIN 19 // esp pin

// pulse length measurements are done at 50HZ for 12bit pwm (100% duty is 4096)
// l'input dei servomotori degli occhi corrisponde~ al valore in gradi dell'angolo
#define EYELID_DR_PULSE_MIN 92
#define EYELID_DR_PULSE_MAX 439
#define EYELID_UR_PULSE_MIN 130
#define EYELID_UR_PULSE_MAX 470
#define EYELID_DL_PULSE_MIN 94
#define EYELID_DL_PULSE_MAX 454
#define EYELID_UL_PULSE_MIN 125
#define EYELID_UL_PULSE_MAX 481
#define EYE_R_PULSE_MIN 113
#define EYE_R_PULSE_MAX 477
#define EYE_L_PULSE_MIN 103
#define EYE_L_PULSE_MAX 466
#define EYE_TILT_PULSE_MIN 140
#define EYE_TILT_PULSE_MAX 400

// il range di input delle orecchie va da -100 (in avanti) a 100 (in dietro). 0 è il punto centrale
#define EAR_LEFT_PULSE_MIN 270
#define EAR_LEFT_PULSE_MID 310
#define EAR_LEFT_PULSE_MAX 360
#define _EAR_L_INPUT_SLOPE (EAR_LEFT_PULSE_MAX - EAR_LEFT_PULSE_MID) * 0.01
#define EAR_RIGHT_PULSE_MIN 130
#define EAR_RIGHT_PULSE_MID 175
#define EAR_RIGHT_PULSE_MAX 220
#define _EAR_R_INPUT_SLOPE -(EAR_LEFT_PULSE_MAX - EAR_LEFT_PULSE_MID) * 0.01

// il range di input della bocca va da 0 (chiusa) a 1000 (tutta aperta)
#define MOUTH_PULSE_MIN 220
#define MOUTH_PULSE_MAX 325

#define NECK_R_PULSE_MIN
#define NECK_R_PULSE_MID
#define NECK_R_PULSE_MAX
#define NECK_L_PULSE_MIN
#define NECK_R_PULSE_MID
#define NECK_L_PULSE_MAX

// valori di lerp default
#define LERP_VALUES_DEFAULT {1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, .01, .01, .01, .01}

