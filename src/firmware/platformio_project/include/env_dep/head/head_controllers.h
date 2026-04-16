#pragma once
#include <Arduino.h>
//#include "hardware/drivers.h"

class EyelidsController {
private:
    PWMServo<int16_t>* lid_up;
    PWMServo<int16_t>* lid_down;
    uint16_t wideness = 0;
    int16_t angle = 0;

    void _update() const {
        lid_up->move(angle + wideness);
        lid_down->move(angle - wideness);
    }

public:
    EyelidsController(PWMServo<int16_t>* lid_up, PWMServo<int16_t>* lid_down) : lid_up(lid_up), lid_down(lid_down) {}

    void set_angle(int16_t ang) {angle = ang; _update();}
    void set_wideness(uint16_t degrees) {wideness = degrees; _update();}
};