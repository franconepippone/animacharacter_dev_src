#pragma once
#include <Arduino.h>

#define MAX_12BIT_PWM_VALUE 4095

typedef uint16_t pulse12bit;

inline pulse12bit get_validPWM12(int in) {return (pulse12bit)constrain(in, 0, MAX_12BIT_PWM_VALUE);}
inline pulse12bit get_validPWM12(float in) {return (pulse12bit)constrain(in, 0.0, (float)MAX_12BIT_PWM_VALUE);}
inline pulse12bit get_validPWM12(double in) {return (pulse12bit)constrain(in,(double)0.0, (double)MAX_12BIT_PWM_VALUE);}

class PWM12Device {
public:
    PWM12Device(uint16_t channel) : channel(channel), min_pulse(0), max_pulse(MAX_12BIT_PWM_VALUE) {};
    PWM12Device(uint16_t channel, pulse12bit _min_pulse, pulse12bit _max_pulse) : channel(channel), 
    min_pulse(_min_pulse < MAX_12BIT_PWM_VALUE ? _min_pulse : MAX_12BIT_PWM_VALUE), 
    max_pulse(_max_pulse < MAX_12BIT_PWM_VALUE ? _max_pulse : MAX_12BIT_PWM_VALUE) {
        write_pulse(min_pulse);
    };

    inline void write_pulse(pulse12bit pulse) {pulselen = constrain(pulse, min_pulse, max_pulse);}
    inline pulse12bit read_pulse() const {return pulselen;}
    inline pulse12bit get_min_pulse() const {return min_pulse;}
    inline pulse12bit get_max_pulse() const {return max_pulse;}
    inline uint16_t get_channel() const {return channel;}

protected:
    uint16_t channel = 0;
    pulse12bit pulselen = 0;
    const pulse12bit min_pulse = 0;
    const pulse12bit max_pulse = MAX_12BIT_PWM_VALUE;
};


template <class IN_T = int16_t>
class PWMServo : public PWM12Device {
protected:
    // default mapping function : f(x) = x
    pulse12bit (*input_map)(IN_T) = [] (IN_T input) -> uint16_t {
        return (pulse12bit)constrain(input, (int16_t)0, (int16_t)MAX_12BIT_PWM_VALUE);
    };

    float lerp_amount = 0.5;
    float smooth_pulse = 0.0;

public: 
    PWMServo(uint16_t channel) : PWM12Device(channel) {};
    PWMServo(uint16_t channel, pulse12bit min_pulse, pulse12bit max_pulse) : PWM12Device(channel, min_pulse, max_pulse) {};
    PWMServo(uint16_t channel, pulse12bit min_pulse, pulse12bit max_pulse, pulse12bit (*input_map_func)(IN_T)) : PWM12Device(channel, min_pulse, max_pulse) 
    {
      input_map = input_map_func;  
    };

    // funzioni da implementare per il lerping
    inline pulse12bit read_smooth_pulse() {return (pulse12bit)smooth_pulse;}
    inline void update_smooth_pulse(float dt) {smooth_pulse += dt * (pulselen - smooth_pulse) * lerp_amount;}

    inline void set_lerp(float val) {lerp_amount = constrain(val, 0.0, 1.0);}
    inline float get_lerp() {return lerp_amount;}

    void move(IN_T input) {
        // ensures input pulse stays in the range of uint16
        write_pulse((*input_map)(input));
    }
};