#pragma once
#include <Arduino.h>

class Timer {
    /* Simple millis()-based timer (rollover safe). */
public:
    Timer(unsigned long durationMs) : duration(durationMs), startTime(0) {}

    // Start or restart the timer. Optionally update duration.
    void start(unsigned long durationMs = 0) {
        if (durationMs > 0) duration = durationMs;
        startTime = millis();
    }

    // True if the timeout has elapsed (does NOT reset the timer).
    bool timedOut() const {
        return (millis() - startTime) >= duration;
    }

    // True once when expired, then automatically restarts the timer.
    bool expired() {
        if (timedOut()) {
            start();
            return true;
        }
        return false;
    }

    // Force the timer to appear expired immediately.
    void fire() {
        startTime = millis() - duration;
    }

private:
    unsigned long duration;   // timeout length in ms
    unsigned long startTime;  // time when the timer started
};