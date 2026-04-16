#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_PWMServoDriver.h>

#include "hardware/led_driver.h"

#include "app/constants.h"
#include "app/head_controllers.h"
#include "app/psp_configs.h"
#include "app/servos_creation.h"

// pca 9685
Adafruit_PWMServoDriver pwm(0x40);

// pwm sources that drive iris light transistors
pwmLedDriver light_R(IRIS_R_PIN);
pwmLedDriver light_L(IRIS_L_PIN);

/// @brief Drives the pwm signal to the servo motors through the pca9685 driver
/// @param dt delta-time, used to smooth out servo movements
void driveServos(float dt) {
  for (size_t i = 0; i < servo_amount; i++) {
    pulse12bit pulse;
    // decides to use either smooth or direct pulse
    if (servos[i]->get_lerp() == 1.0) {
        pulse = servos[i]->read_pulse();
    } else {
        servos[i]->update_smooth_pulse(dt);
        pulse = servos[i]->read_smooth_pulse();
    }
    // TODO update this with only one transaction at the end
    pwm.setPWM(servos[i]->get_channel(), 0, pulse);
  }
}

void set_rgb(uint16_t r, uint16_t g, uint16_t b) {
    pwm.setPWM(CHANNEL_LED_R, 0, r);
    pwm.setPWM(CHANNEL_LED_G, 0, g);
    pwm.setPWM(CHANNEL_LED_B, 0, b);
}

/// @brief Initializes all hardware (pca9685, lights PWM pins), returns 0 on success
int initializeHardware() {
    pwm.begin();
    pwm.setOscillatorFrequency(27000000);
    pwm.setPWMFreq(SERVO_FREQ);  // Analog servos run at ~50 Hz updates

    light_R.init();
    light_L.init();

    return 0;
}

void deinitializeHardware() {
    for (uint8_t i = 0; i < 16; i++) {
    pwm.setPWM(i, 0, 0);  // Set all channels to 0 (stop sending PWM signal)
    }
    pwm.reset();

    light_R.deinit();
    light_L.deinit();
}

void updateHardare() {
    // eyes
    eyeLeft.set_angle(head_control_vars.eye_tilt);
    eyeRight.set_angle(head_control_vars.eye_tilt);
    eyeLeft.set_wideness(head_control_vars.eyelid_l_wideness);
    eyeRight.set_wideness(head_control_vars.eyelid_r_wideness);
    SERVO_EYE_TILT.move(head_control_vars.eye_tilt);
    SERVO_EYE_L.move(head_control_vars.eye_left);
    SERVO_EYE_R.move(head_control_vars.eye_right);

    // ears
    SERVO_EAR_RIGHT.move(head_control_vars.ear_r);
    SERVO_EAR_LEFT.move(head_control_vars.ear_l);

    // neck
    SERVO_NECK_RIGHT.move(head_control_vars.neck_r);
    SERVO_NECK_LEFT.move(head_control_vars.neck_l);

    // mouth
    mouth.write_pulse(map(head_control_vars.mouth, 0, 256, MOUTH_PULSE_MIN, MOUTH_PULSE_MAX));

    //lights
    if (head_leds_vars.has_changed) {
        set_rgb(head_leds_vars.r, head_leds_vars.g, head_leds_vars.b);
        light_L.setDuty(head_leds_vars.lightL);
        light_R.setDuty(head_leds_vars.lightR);
        head_leds_vars.has_changed = false;
    }

    // drives all servos with dt of 1.0 (to be updated with real dt if needed)
    driveServos(1.0);
}