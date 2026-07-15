#include <Arduino.h>
#include <LiquidCrystal.h>

// RS, E, D4, D5, D6, D7
LiquidCrystal lcd(12, 11, 5, 4, 3, 2);

void setup() {
  lcd.begin(16, 2);          // Initialize a 16x2 LCD
  lcd.print("Hello, world!"); // Write on the first line
}

void loop() {
  lcd.setCursor(0, 1);        // Move to column 0, row 1
  lcd.print("LCD Test");      // Write on the second line
}
