#include <SerialDevice.h>
#include <Arduino.h>
//#include <ezLED.h>

SerialDevice dev(Serial, "ANIM1:HEAD");

//ezLED led(LED_BUILTIN);

byte largeRxBuffer[80] = {1, 2, 3, 4, 5}; // buffer for large transfer reception


void setup()
{
  dev.begin(115200);
  delay(200);

  _debug_blink_builtin(3, 100);
  //led.blink(500, 800);
  // binds cb
  dev.configLargeRx(largeRxBuffer, sizeof(largeRxBuffer));
}



void loop()
{
  dev.poll();
  //led.loop();
}