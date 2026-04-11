#pragma once
#include <Arduino.h>

/*Drive pwm signal on desired pin of the esp32 board, using the ledc interface. Pwm source channel is automatically
choosen (up to 8 channels). N.B.: PWM frequency and resolution are interdependent. The higher the PWM frequency, the lower the duty cycle resolution (and vice versa).
Unless required, leave 'freq' and 'resolution' to their default.

@param pin pin on the esp32 board on wich to output the pwm waveform.
@param freq frequency of pwm.
@param resolution resolution of pwm (measured in bits).*/
class pwmLedDriver {
private:
  const uint8_t pin;
  const uint freq;
  const uint pwmres;

public:
/*Drive pwm signal on desired pin of the esp32 board, using the ledc interface. Pwm source channel is automatically
choosen (up to 8 channels). N.B.: PWM frequency and resolution are interdependent. The higher the PWM frequency, the lower the duty cycle resolution (and vice versa).
Unless required, leave 'freq' and 'resolution' to their default.

@param pin pin on the esp32 board on wich to output the pwm waveform.
@param freq frequency of pwm.
@param resolution resolution of pwm (measured in bits).*/
  pwmLedDriver(int pin, uint freq = 500, uint resolution = 8);
  
  //initialize internal pwm source channel and attaches pin.
  bool init();
  bool deinit();
  const int getPin();
  const int getChannel();
  const int getFreq();
  const int getResolution();
  const uint32_t getMaxDutyCycle();

  // Refert to 'getMaxDutyCycle' to find out the maximum available 'duty' value.
  void setDuty(uint duty);
};