/**
 * Nova Animatronic - Calibration & Setup Tool
 * 
 * This sketch helps you identify which servo is connected to which pin.
 * It will safely move each servo one by one and ask you to name it.
 * 
 * INSTRUCTIONS:
 * 1. Upload this sketch to your Arduino Mega.
 * 2. Open the Serial Monitor (Tools > Serial Monitor).
 * 3. Set Baud Rate to 9600.
 * 4. Select "Both NL & CR" or "Newline" in the dropdown.
 * 5. Follow the on-screen prompts.
 */

#include <Servo.h>

// The pins you believe are connected
const int PINS[] = {4, 5, 6, 7, 8};
const int NUM_PINS = 5;

// Variables to store results
String pinNames[NUM_PINS];
Servo tester;

// Default safe range (degrees)
// Chosen to be safe for Jaw (30-110), Eye H (40-110), Eye V (70-180), Neck (30-110)
int minAngle = 80;
int maxAngle = 100;

void setup() {
  Serial.begin(9600);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB
  }
  
  Serial.println("\n\n=========================================");
  Serial.println("      NOVA ANIMATRONIC CALIBRATION       ");
  Serial.println("=========================================");
  Serial.println("This tool will help you map your pins.");
  Serial.print("Checking pins: ");
  for(int i=0; i<NUM_PINS; i++) {
    Serial.print(PINS[i]);
    if(i < NUM_PINS-1) Serial.print(", ");
  }
  Serial.println("\n");

  // --- Step 1: Range Configuration ---
  Serial.println("STEP 1: SAFETY CONFIGURATION");
  Serial.println("Default safe movement range is 80 to 100 degrees.");
  Serial.println("This range is generally safe for all Nova parts.");
  Serial.println("-> Send 's' to START with default range.");
  Serial.println("-> Or send 'min max' (e.g., '30 60') to specify custom range.");
  
  while (Serial.available() == 0) {} // Wait for input
  String input = Serial.readStringUntil('\n');
  input.trim();
  
  if (input.length() > 1 && input.indexOf(' ') > 0) {
    // Parse custom range
    int spaceIdx = input.indexOf(' ');
    minAngle = input.substring(0, spaceIdx).toInt();
    maxAngle = input.substring(spaceIdx+1).toInt();
    Serial.print("✅ Custom range set: ");
  } else {
    Serial.print("✅ Default range used: ");
  }
  Serial.print(minAngle);
  Serial.print(" - ");
  Serial.println(maxAngle);
  delay(1000);

  // --- Step 2: Testing Loop ---
  Serial.println("\nSTEP 2: IDENTIFICATION");
  Serial.println("I will now move each pin. Watch the robot!");
  Serial.println("Enter the name: 'neck', 'jaw', 'eye', 'z' (for tilt), or 'none'.");
  Serial.println("-----------------------------------------");

  for (int i = 0; i < NUM_PINS; i++) {
    int currentPin = PINS[i];
    Serial.print("\n👉 Testing PIN ");
    Serial.print(currentPin);
    Serial.println("...");
    
    tester.attach(currentPin);
    
    // Wiggle sequence
    for (int j = 0; j < 3; j++) {
      tester.write(minAngle);
      delay(400);
      tester.write(maxAngle);
      delay(400);
    }
    // Return to center of range
    tester.write((minAngle + maxAngle) / 2);
    
    Serial.print("   Pin ");
    Serial.print(currentPin);
    Serial.println(" moved. What is it? (neck/jaw/eye/z/none)");
    
    while (Serial.available() == 0) {} // Wait for input
    String name = Serial.readStringUntil('\n');
    name.trim();
    name.toLowerCase();
    
    pinNames[i] = name;
    Serial.print("   Saved: Pin ");
    Serial.print(currentPin);
    Serial.print(" = ");
    Serial.println(name);
    
    tester.detach(); // Detach to prevent interference
    delay(500);
  }

  // --- Step 3: Report ---
  Serial.println("\n\n=========================================");
  Serial.println("           CALIBRATION COMPLETE          ");
  Serial.println("=========================================");
  Serial.println("Copy the lines below into your main 'nova_arduino.ino' file:");
  Serial.println("-----------------------------------------");
  
  for (int i = 0; i < NUM_PINS; i++) {
    if (pinNames[i] != "none" && pinNames[i] != "") {
      String varName = "PIN_UNKNOWN";
      if (pinNames[i] == "neck") varName = "PIN_NECK";
      else if (pinNames[i] == "jaw") varName = "PIN_JAW";
      else if (pinNames[i] == "eye") varName = "PIN_EYE";
      else if (pinNames[i] == "z") varName = "PIN_Z";
      else if (pinNames[i] == "eye z") varName = "PIN_Z";
      
      Serial.print("const int ");
      Serial.print(varName);
      Serial.print(" = ");
      Serial.print(PINS[i]);
      Serial.println(";");
    }
  }
  Serial.println("-----------------------------------------");
  Serial.println("Done!");
}

void loop() {
  // Nothing to do here
}
