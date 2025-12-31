#pragma once
#include <Arduino.h>

class Timer {
    /*Simple utility class to handle timeouts.*/
    public:
        Timer(unsigned long durationMs) : duration(durationMs), fireTime(0) {}
    
        void start(unsigned long durationMs = 0) {
            if (durationMs > 0) duration = durationMs;
            fireTime = millis() + duration;
        }
    
        bool timedOut() {
            return millis() >= fireTime;
        }
    
    private:
        unsigned long duration;
        unsigned long fireTime;
    };