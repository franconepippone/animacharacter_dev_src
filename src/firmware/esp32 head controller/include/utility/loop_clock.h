#include <Arduino.h>

/// @brief Helper object to help stabilize looping frequency
class Clock {
private:
  uint64_t deltatime = 0;
  uint64_t temp = 0;

public:
  Clock() {temp = micros();}

  /// @brief waits until the specified time has passed since last call
  uint32_t tick_ms(uint64_t ms) {return tick_us(ms * 1000);}
  uint32_t tick_hz(float freq) {return tick_us((uint64_t) (1000000 / freq));}

  uint32_t tick_us(uint64_t us) {
    deltatime = micros() - temp;

    //avoid negative subctractions with unsigned integers
    if (deltatime < us) delayMicroseconds(us - deltatime);
    temp = micros();
    return deltatime;
  } 
};