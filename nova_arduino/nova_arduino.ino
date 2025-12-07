/**
 * Nova Animatronic - Final Firmware
 * 
 * This sketch controls the Nova animatronic head.
 * It listens for serial commands from the Python host and moves the servos.
 * 
 * PINS:
 * Update the numbers below to match your calibration results!
 */

#include <Servo.h>

// --- PIN CONFIGURATION (UPDATE THESE!) ---
// Based on your calibration, assign the correct pin number to each part.
// You mentioned pins 4, 5, 6, 7, 8 are connected.
const int PIN_EYE  = 4;  // Horizontal Eye Turn
const int PIN_JAW  = 5;  // Mouth
const int PIN_NECK = 6;  // Horizontal Head Turn
const int PIN_Z    = 7;  // Vertical Head Tilt (Up/Down)
// const int PIN_AUX = 8; // Extra pin if needed

// --- SERVO SETTINGS ---
const int BAUD_RATE = 9600;

// Initial Positions (Degrees)
const int INIT_NECK = 80;  // Center
const int INIT_JAW  = 30;  // Closed
const int INIT_EYE  = 80;  // Center
const int INIT_Z    = 130; // Level

// Safety Limits (Degrees)
// These prevent the servos from hitting mechanical stops.
const int MIN_ANGLE = 0;
const int MAX_ANGLE = 180;

// JAW SPEED CONTROL
// Increase this value to slow down jaw movement, decrease to speed up.
// 6ms per degree = ~166 degrees/second (smooth but responsive)
const int JAW_UPDATE_DELAY_MS = 6;

// Servo Objects
Servo servoNeck;
Servo servoJaw;
Servo servoEye;
Servo servoZ;

// Jaw Movement State (for smooth animation)
int currentJawAngle = INIT_JAW;
int targetJawAngle = INIT_JAW;
unsigned long lastJawUpdateTime = 0;

// Serial Buffer
String inputString = "";
boolean stringComplete = false;

void setup() {
  // 1. Initialize Serial
  Serial.begin(BAUD_RATE);
  
  // 2. Attach Servos
  servoNeck.attach(PIN_NECK);
  servoJaw.attach(PIN_JAW);
  servoEye.attach(PIN_EYE);
  servoZ.attach(PIN_Z);
  
  // 3. Move to Start Positions
  servoNeck.write(INIT_NECK);
  servoJaw.write(INIT_JAW);
  servoEye.write(INIT_EYE);
  servoZ.write(INIT_Z);
  
  // 4. Prepare Buffer
  inputString.reserve(200);
  
  // 5. Signal Ready (Blink onboard LED)
  pinMode(13, OUTPUT);
  digitalWrite(13, HIGH);
  delay(500);
  digitalWrite(13, LOW);
}

void loop() {
  // --- SMOOTH JAW MOVEMENT ---
  // Move jaw incrementally toward target angle for smoother animation
  unsigned long currentTime = millis();
  if (currentTime - lastJawUpdateTime >= JAW_UPDATE_DELAY_MS) {
    lastJawUpdateTime = currentTime;
    
    if (currentJawAngle < targetJawAngle) {
      currentJawAngle++;
      servoJaw.write(currentJawAngle);
    } 
    else if (currentJawAngle > targetJawAngle) {
      currentJawAngle--;
      servoJaw.write(currentJawAngle);
    }
  }
  
  // --- SERIAL COMMAND PROCESSING ---
  if (stringComplete) {
    processCommand(inputString);
    
    // Clear
    inputString = "";
    stringComplete = false;
    
    // Send Acknowledgement
    Serial.println("K");
  }
}

// --- SERIAL EVENT HANDLER ---
void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar != '\n') {
      inputString += inChar;
    } else {
      stringComplete = true;
    }
  }
}

// --- COMMAND PROCESSOR ---
void processCommand(String command) {
  command.trim();
  int spaceIndex = command.indexOf(' ');
  if (spaceIndex == -1) return;
  
  String cmdType = command.substring(0, spaceIndex);
  int angle = command.substring(spaceIndex + 1).toInt();
  
  // Safety Constraint
  angle = constrain(angle, MIN_ANGLE, MAX_ANGLE);
  
  if (cmdType.equalsIgnoreCase("neck")) {
    servoNeck.write(angle);
  } 
  else if (cmdType.equalsIgnoreCase("jaw")) {
    // Set target angle only - loop() handles smooth movement
    targetJawAngle = angle;
  } 
  else if (cmdType.equalsIgnoreCase("eye")) {
    servoEye.write(angle);
  } 
  else if (cmdType.equalsIgnoreCase("z")) {
    servoZ.write(angle);
  }
}
