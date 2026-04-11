#pragma once
#include <Arduino.h>

#include <hardware/pwm_devices.h>

/* Permette di controllare due canali PWM simmetricamente.
i.e.: due servomotori che agiscono a specchio su uno stesso asse di rotazione.

Il pulse_midpoint è il PWM in cui i due attuatori si allineano perfettamente; NB se si vuole controllare 
dei servomotori è importante trovare sperimentalmente il pulse_midpoint correttamente per evitare di
danneggiare i motori una volta accesi. 
*/
class SimmetricPWM12Pair {
public:
    SimmetricPWM12Pair(PWM12Device &actuator_primary, PWM12Device &actuator_slave, pulse12bit pulse_midpoint) :
    actuator_primary(&actuator_primary), actuator_slave(&actuator_slave), pulse_midpoint(pulse_midpoint) {
        // calculates the maximum range of motion from the limits of the given actuators
        pulse_min = pulse_midpoint - min(pulse_midpoint - actuator_primary.get_min_pulse(), actuator_slave.get_max_pulse() - pulse_midpoint);
        pulse_max = pulse_midpoint + min(actuator_primary.get_max_pulse() - pulse_midpoint, pulse_midpoint - actuator_slave.get_min_pulse());
    }

    // NOTE: Pulse must be higher than the lowest of the acutator's minimum PWM and lower than the highest of the actuator's maximum PWM!
    void write_pulse(pulse12bit pulse) {
        int deltapulse = (int)constrain(pulse, pulse_min, pulse_max) - pulse_midpoint;
        actuator_primary->write_pulse(pulse_midpoint + deltapulse);
        actuator_slave-> write_pulse(pulse_midpoint - deltapulse);
    }
    
    inline pulse12bit get_min_pulse() const {return pulse_min;}
    inline pulse12bit get_max_pulse() const {return pulse_max;}
    inline PWM12Device* get_primary_actuator() {return actuator_primary;}
    inline PWM12Device* get_slave_actuator() {return actuator_slave;}

private:
    PWM12Device* actuator_primary;
    PWM12Device* actuator_slave;
    int16_t pulse_midpoint;
    pulse12bit pulse_min;
    pulse12bit pulse_max;
};