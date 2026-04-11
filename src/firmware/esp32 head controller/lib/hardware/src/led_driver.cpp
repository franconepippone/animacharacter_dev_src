#include <Arduino.h>
#include "hardware/led_driver.h"

pwmLedDriver::pwmLedDriver(int pin, uint freq, uint resolution) : pin(pin), freq(freq), pwmres(resolution) {}

bool pwmLedDriver::init() {
  return ledcAttach(pin, freq, pwmres);
}

bool pwmLedDriver::deinit() {
  return ledcDetach(pin);
}

const int pwmLedDriver::getPin() {return pin;}
const int pwmLedDriver::getFreq() {return freq;}
const int pwmLedDriver::getResolution() {return pwmres;}

const uint32_t pwmLedDriver::getMaxDutyCycle() {return (int)(pow(2, pwmres) - 1);}

// Refert to 'getMaxDutyCycle' to find out the maximum available 'duty' value.
void pwmLedDriver::setDuty(uint duty) {
    ledcWrite(pin, duty);
}




/*SAMPLE CODE
const int DELAY_MS = 4;  // delay between fade increments

pwmLedDriver ringlight(18);
pwmDriver   
int MAX_DUTY_CYCLE = ringlight.getMaxDutyCycle();

void xsetup() {
  ringlight.begin();
  Serial.begin(9600);
  Serial.println(ringlight.getChannel());
  Serial.println(ringlight.getFreq());
  Serial.println(ringlight.getPin());
  Serial.println(ringlight.getResolution());

  
}

void sloop() {

  // fade up PWM on given channel
  for(int dutyCycle = 0; dutyCycle <= MAX_DUTY_CYCLE; dutyCycle++){   
    ringlight.setDuty(dutyCycle);
    delay(DELAY_MS);
  }
  delay(200);
  // fade down PWM on given channel
  for(int dutyCycle = MAX_DUTY_CYCLE; dutyCycle >= 0; dutyCycle--){
    ringlight.setDuty(dutyCycle);  
    delay(DELAY_MS);
  }
  delay(500);
  ringlight.setDuty(1);
  delay(500);
  ringlight.setDuty(255);
  delay(2000);  
}*/