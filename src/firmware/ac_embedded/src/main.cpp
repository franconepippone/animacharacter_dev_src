#include <Arduino.h>

#ifndef LED_BUILTIN
    #define LED_BUILTIN 2
#endif

// put function declarations here:
int myFunction(int, int);

void setup() {
  // put your setup code here, to run once:
  int result = myFunction(2, 3);
}

void loop() {
  // put your main code here, to run repeatedly:
  digitalWrite(LED_BUILTIN, 1);
  ledcAttachPin()
}



// put function definitions here:
int myFunction(int x, int y) {
  return x + y;
}