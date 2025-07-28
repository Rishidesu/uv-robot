# ESP32 Robot Integration Guide

## Current App API Endpoints

Your robot control app is running at: `https://cacf2a31-9e35-4049-85ee-3b36c7bcc84a.preview.emergentagent.com`

### Available API Endpoints:
- `GET /api/robot/status` - Get current robot commands
- `POST /api/robot/status` - Send robot status updates  
- `POST /api/robot/command` - Receive commands from app
- `WebSocket /api/ws` - Real-time communication

## Integration Approach 1: HTTP REST API (Recommended)

### ESP32 Arduino Code Example:

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <NewPing.h>

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// API endpoints
const char* apiBase = "https://cacf2a31-9e35-4049-85ee-3b36c7bcc84a.preview.emergentagent.com/api";
String robotId = "robot_001"; // Unique robot identifier

// Hardware pins
#define TRIGGER_PIN_1  12
#define ECHO_PIN_1     14
#define TRIGGER_PIN_2  27
#define ECHO_PIN_2     26
#define TRIGGER_PIN_3  25
#define ECHO_PIN_3     33

#define MOTOR_LEFT_PWM   18
#define MOTOR_LEFT_DIR1  19
#define MOTOR_LEFT_DIR2  21
#define MOTOR_RIGHT_PWM  22
#define MOTOR_RIGHT_DIR1 23
#define MOTOR_RIGHT_DIR2 5

#define UV_LED_PIN      2
#define SPRAY_PUMP_PIN  4
#define MOP_MOTOR_PIN   16

// Ultrasonic sensors
NewPing sonar1(TRIGGER_PIN_1, ECHO_PIN_1, 200);
NewPing sonar2(TRIGGER_PIN_2, ECHO_PIN_2, 200);
NewPing sonar3(TRIGGER_PIN_3, ECHO_PIN_3, 200);

// Robot state
struct RobotState {
  String status = "idle";           // idle, mopping, spraying, uv_disinfecting, paused
  int progress = 0;                 // 0-100
  bool is_cleaning = false;
  bool obstacle_detected = false;
  String current_mode = "";
  unsigned long start_time = 0;
} robotState;

// Command from app
struct Command {
  String command = "";              // start, stop, pause, resume
  String mode = "";                 // full_clean, mop_only, spray_only, uv_only
  bool hasNewCommand = false;
} currentCommand;

void setup() {
  Serial.begin(115200);
  
  // Initialize pins
  pinMode(UV_LED_PIN, OUTPUT);
  pinMode(SPRAY_PUMP_PIN, OUTPUT);
  pinMode(MOP_MOTOR_PIN, OUTPUT);
  pinMode(MOTOR_LEFT_PWM, OUTPUT);
  pinMode(MOTOR_LEFT_DIR1, OUTPUT);
  pinMode(MOTOR_LEFT_DIR2, OUTPUT);
  pinMode(MOTOR_RIGHT_PWM, OUTPUT);
  pinMode(MOTOR_RIGHT_DIR1, OUTPUT);
  pinMode(MOTOR_RIGHT_DIR2, OUTPUT);
  
  // Connect to WiFi
  connectToWiFi();
  
  Serial.println("Robot initialized and connected!");
}

void loop() {
  // Check for commands from app every 2 seconds
  static unsigned long lastCommandCheck = 0;
  if (millis() - lastCommandCheck > 2000) {
    checkForCommands();
    lastCommandCheck = millis();
  }
  
  // Send status updates every 5 seconds
  static unsigned long lastStatusUpdate = 0;
  if (millis() - lastStatusUpdate > 5000) {
    sendStatusUpdate();
    lastStatusUpdate = millis();
  }
  
  // Main robot logic
  executeCurrentOperation();
  
  // Check for obstacles
  checkObstacles();
  
  delay(100);
}

void connectToWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println();
  Serial.println("WiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void checkForCommands() {
  if (WiFi.status() != WL_CONNECTED) return;
  
  HTTPClient http;
  http.begin(String(apiBase) + "/robot/status");
  http.addHeader("Content-Type", "application/json");
  
  int httpResponseCode = http.GET();
  
  if (httpResponseCode == 200) {
    String response = http.getString();
    
    // Parse JSON response
    DynamicJsonDocument doc(1024);
    deserializeJson(doc, response);
    
    // Check if there's a new command
    if (doc["robot_state"]["has_new_command"]) {
      currentCommand.command = doc["robot_state"]["pending_command"].as<String>();
      currentCommand.mode = doc["robot_state"]["pending_mode"].as<String>();
      currentCommand.hasNewCommand = true;
      
      Serial.println("New command received: " + currentCommand.command);
    }
  }
  
  http.end();
}

void sendStatusUpdate() {
  if (WiFi.status() != WL_CONNECTED) return;
  
  HTTPClient http;
  http.begin(String(apiBase) + "/robot/status");
  http.addHeader("Content-Type", "application/json");
  
  // Create JSON payload
  DynamicJsonDocument doc(1024);
  doc["robot_id"] = robotId;
  doc["status"] = robotState.status;
  doc["progress"] = robotState.progress;
  doc["is_cleaning"] = robotState.is_cleaning;
  doc["obstacle_detected"] = robotState.obstacle_detected;
  doc["current_mode"] = robotState.current_mode;
  doc["uptime"] = millis();
  
  // Add sensor readings
  doc["sensors"]["ultrasonic_1"] = sonar1.ping_cm();
  doc["sensors"]["ultrasonic_2"] = sonar2.ping_cm();
  doc["sensors"]["ultrasonic_3"] = sonar3.ping_cm();
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  int httpResponseCode = http.POST(jsonString);
  
  if (httpResponseCode == 200) {
    Serial.println("Status update sent successfully");
  } else {
    Serial.println("Failed to send status update: " + String(httpResponseCode));
  }
  
  http.end();
}

void executeCurrentOperation() {
  // Process new commands
  if (currentCommand.hasNewCommand) {
    processCommand(currentCommand.command, currentCommand.mode);
    currentCommand.hasNewCommand = false;
  }
  
  // Execute cleaning operations based on current state
  if (robotState.is_cleaning && !robotState.obstacle_detected) {
    
    if (robotState.status == "mopping") {
      performMopping();
    }
    else if (robotState.status == "spraying") {
      performSpraying();
    }
    else if (robotState.status == "uv_disinfecting") {
      performUVDisinfection();
    }
    
    // Update progress (simplified - adjust based on your logic)
    static unsigned long progressTimer = 0;
    if (millis() - progressTimer > 10000) { // Update every 10 seconds
      robotState.progress = min(robotState.progress + 5, 100);
      progressTimer = millis();
      
      // Check if cleaning is complete
      if (robotState.progress >= 100) {
        stopCleaning();
      }
    }
  }
}

void processCommand(String command, String mode) {
  Serial.println("Processing command: " + command + " mode: " + mode);
  
  if (command == "start") {
    startCleaning(mode);
  }
  else if (command == "stop") {
    stopCleaning();
  }
  else if (command == "pause") {
    pauseCleaning();
  }
  else if (command == "resume") {
    resumeCleaning();
  }
}

void startCleaning(String mode) {
  robotState.is_cleaning = true;
  robotState.current_mode = mode;
  robotState.progress = 0;
  robotState.start_time = millis();
  
  if (mode == "full_clean") {
    robotState.status = "mopping";
  }
  else if (mode == "mop_only") {
    robotState.status = "mopping";
  }
  else if (mode == "spray_only") {
    robotState.status = "spraying";
  }
  else if (mode == "uv_only") {
    robotState.status = "uv_disinfecting";
  }
  
  Serial.println("Started cleaning: " + mode);
}

void stopCleaning() {
  robotState.is_cleaning = false;
  robotState.status = "idle";
  robotState.progress = 0;
  robotState.current_mode = "";
  
  // Stop all hardware
  stopAllMotors();
  digitalWrite(UV_LED_PIN, LOW);
  digitalWrite(SPRAY_PUMP_PIN, LOW);
  digitalWrite(MOP_MOTOR_PIN, LOW);
  
  Serial.println("Cleaning stopped");
}

void pauseCleaning() {
  if (robotState.is_cleaning) {
    robotState.status = "paused";
    stopAllMotors();
    digitalWrite(UV_LED_PIN, LOW);
    digitalWrite(SPRAY_PUMP_PIN, LOW);
    digitalWrite(MOP_MOTOR_PIN, LOW);
    
    Serial.println("Cleaning paused");
  }
}

void resumeCleaning() {
  if (robotState.is_cleaning && robotState.status == "paused") {
    // Resume based on current mode
    if (robotState.current_mode == "full_clean") {
      robotState.status = "mopping"; // or determine based on progress
    }
    else if (robotState.current_mode == "mop_only") {
      robotState.status = "mopping";
    }
    else if (robotState.current_mode == "spray_only") {
      robotState.status = "spraying";
    }
    else if (robotState.current_mode == "uv_only") {
      robotState.status = "uv_disinfecting";
    }
    
    Serial.println("Cleaning resumed");
  }
}

void checkObstacles() {
  const int OBSTACLE_THRESHOLD = 20; // cm
  
  int distance1 = sonar1.ping_cm();
  int distance2 = sonar2.ping_cm();
  int distance3 = sonar3.ping_cm();
  
  bool obstacleDetected = (distance1 > 0 && distance1 < OBSTACLE_THRESHOLD) ||
                         (distance2 > 0 && distance2 < OBSTACLE_THRESHOLD) ||
                         (distance3 > 0 && distance3 < OBSTACLE_THRESHOLD);
  
  if (obstacleDetected && !robotState.obstacle_detected && robotState.is_cleaning) {
    robotState.obstacle_detected = true;
    pauseCleaning();
    Serial.println("Obstacle detected! Pausing...");
  }
  else if (!obstacleDetected && robotState.obstacle_detected) {
    robotState.obstacle_detected = false;
    
    // Auto-resume after 3 seconds
    static unsigned long obstacleTimer = 0;
    if (millis() - obstacleTimer > 3000) {
      resumeCleaning();
      Serial.println("Path clear, resuming...");
    }
  }
}

void performMopping() {
  // Run mop motor
  digitalWrite(MOP_MOTOR_PIN, HIGH);
  
  // Move robot in mopping pattern
  moveForward(150); // Adjust speed as needed
  
  // Add your mopping logic here
}

void performSpraying() {
  // Turn on spray pump
  digitalWrite(SPRAY_PUMP_PIN, HIGH);
  
  // Move robot for spraying
  moveForward(100);
  
  // Add your spraying logic here
}

void performUVDisinfection() {
  // Turn on UV-C LEDs
  digitalWrite(UV_LED_PIN, HIGH);
  
  // Move slowly for UV exposure
  moveForward(80);
  
  // Add your UV disinfection logic here
}

void moveForward(int speed) {
  // Left motor forward
  digitalWrite(MOTOR_LEFT_DIR1, HIGH);
  digitalWrite(MOTOR_LEFT_DIR2, LOW);
  analogWrite(MOTOR_LEFT_PWM, speed);
  
  // Right motor forward
  digitalWrite(MOTOR_RIGHT_DIR1, HIGH);
  digitalWrite(MOTOR_RIGHT_DIR2, LOW);
  analogWrite(MOTOR_RIGHT_PWM, speed);
}

void stopAllMotors() {
  analogWrite(MOTOR_LEFT_PWM, 0);
  analogWrite(MOTOR_RIGHT_PWM, 0);
}
```

## Integration Approach 2: WebSocket Real-time

For real-time bidirectional communication:

```cpp
#include <WebSocketsClient.h>

WebSocketsClient webSocket;

void setupWebSocket() {
  webSocket.begin("cacf2a31-9e35-4049-85ee-3b36c7bcc84a.preview.emergentagent.com", 443, "/api/ws");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_CONNECTED:
      Serial.println("WebSocket Connected");
      break;
      
    case WStype_TEXT:
      handleWebSocketMessage((char*)payload);
      break;
      
    case WStype_DISCONNECTED:
      Serial.println("WebSocket Disconnected");
      break;
  }
}

void handleWebSocketMessage(String message) {
  DynamicJsonDocument doc(1024);
  deserializeJson(doc, message);
  
  if (doc["type"] == "command") {
    String command = doc["command"];
    String mode = doc["mode"];
    processCommand(command, mode);
  }
}
```

## Required Libraries for ESP32:

Add these to your Arduino IDE Library Manager:
- ArduinoJson (by Benoit Blanchon)
- NewPing (for ultrasonic sensors)
- WebSockets (by Markus Sattler) - if using WebSocket approach

## Testing Integration:

1. Upload the code to your ESP32
2. Monitor Serial output for connection status
3. Use the web app to send commands
4. Verify ESP32 receives and executes commands
5. Check that status updates appear in the web app
