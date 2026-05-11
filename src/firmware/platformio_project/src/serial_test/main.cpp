#include <SerialDevice.h>
#include <Arduino.h>
//#include <ezLED.h>

#include <FastAccelStepper.h>
#include <FastAccelStepperEngine.h>


// Body tilt right stepper
#define PIN_STP_R_EN 2         //enable driver
#define PIN_STP_R_DIR 3        // direction
#define PIN_STP_R_STEP 9       // step
#define PIN_STP_R_WRN 4        // wrn (when motor s)

// Body left tilt stepper
#define PIN_STP_L_EN 5         //enable driver
#define PIN_STP_L_DIR 6        // direction
#define PIN_STP_L_STEP 10       // step
#define PIN_STP_L_WRN 7        // wrn (when motor s)


SerialDevice dev(Serial, "tester-nano");

//byte largeRxBuffer[80] = {1, 2, 3, 4, 5}; // buffer for large transfer reception

FastAccelStepperEngine engine;
FastAccelStepper* stepperR = nullptr;
FastAccelStepper* stepperL = nullptr;


void setup()
{
  Serial.begin(115200);
  dev.begin(115200);
  delay(200);
  Serial.println(F("settupping"));
  engine.init();
  /*stepperL = engine.stepperConnectToPin(PIN_STP_L_STEP);
  stepperL->setEnablePin(PIN_STP_L_EN);
  stepperL->setDirectionPin(PIN_STP_L_DIR);
  stepperL->setSpeedInHz(20000); // max velocity
  stepperL->setAcceleration(10000);
  */
  stepperR = engine.stepperConnectToPin(PIN_STP_R_STEP);
  stepperR->setEnablePin(PIN_STP_R_EN);
  stepperR->setDirectionPin(PIN_STP_R_DIR);
  stepperR->setSpeedInHz(10000); // max velocity
  stepperR->setAcceleration(6000);

  stepperR->enableOutputs();

  Serial.println(F("finishing setupping"));
  _debug_blink_builtin(3, 100);
  
  //led.blink(500, 800);
  // binds cb
  //dev.configLargeRx(largeRxBuffer, sizeof(largeRxBuffer));
}

int POSITIONS[] = {10000, 5000, 0, -1000, -10000};

void loop()
{
  stepperR->moveTo(4000, false);
  delay(200);
  stepperR->moveTo(-4000, true);
  stepperR->moveTo(0, true);
  delay(100);
  //led.loop();
}