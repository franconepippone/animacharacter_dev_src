#include <Arduino.h>
#include <LiquidCrystal.h>
#include <EncoderButton.h>
#include <ezLED.h> 

// lcd display
const uint8_t PIN_LCD_RS = 3;
const uint8_t PIN_LCD_E = 4;
const uint8_t PIN_LCD_D4 = 5;
const uint8_t PIN_LCD_D5 = 6;
const uint8_t PIN_LCD_D6 = 7;
const uint8_t PIN_LCD_D7 = 8;
const uint8_t PIN_LCD_BACKLIGHT = 9;

// encoder
constexpr uint8_t PIN_A = 12;
constexpr uint8_t PIN_B = 11;
constexpr uint8_t PIN_SW = 10;

// signaling
const int PIN_BUZZER = 2; 
const int PIN_LED_GREEN = A3;
const int PIN_LED_RED = 13; // 13 is also LED_BUILTIN, red is for faulty states

// RS, E, D4, D5, D6, D7
LiquidCrystal lcd(PIN_LCD_RS, PIN_LCD_E, PIN_LCD_D4, PIN_LCD_D5, PIN_LCD_D6, PIN_LCD_D7);

EncoderButton eb(PIN_A, PIN_B, PIN_SW);

ezLED led1(PIN_LED_GREEN);  // create ezLED object that attach to pin PIN_LED_1
ezLED led2(PIN_LED_RED);  // create ezLED object that attach to pin PIN_LED_2

void onEncoder(EncoderButton& eb) {
  Serial.println(eb.increment());   // +1 or -1
  if (eb.increment() == 1) {
    tone(PIN_BUZZER, 4000, 10);
  } else {
    tone(PIN_BUZZER, 2000, 10);
  }
}

void onClick(EncoderButton&) {
  Serial.println("Click");
  tone(PIN_BUZZER, 4000, 100);
}

void onLongPress(EncoderButton&) {
  Serial.println("Long press");
  tone(PIN_BUZZER, 2000, 1000);

}

void setup() {
  Serial.begin(115200);

  eb.setEncoderHandler(onEncoder);
  eb.setClickHandler(onClick);
  eb.setLongPressHandler(onLongPress);

  lcd.begin(16, 2);          // Initialize a 16x2 LCD
  lcd.print("Andrea"); // Write on the first line

  led1.blink(100, 500);
  led2.blink(50, 100);

  pinMode(PIN_LCD_BACKLIGHT, OUTPUT);
  digitalWrite(PIN_LCD_BACKLIGHT, HIGH);  // Backlight on

  tone(PIN_BUZZER, 4000, 50);
  delay(100);
  tone(PIN_BUZZER, 4000, 50);

  delay(1000);
}

void loop() {
  led1.loop();
  led2.loop();
  eb.update();
  //tone(DD7, 4000, 1000);
  //delay(2000);
  delay(5);
}
