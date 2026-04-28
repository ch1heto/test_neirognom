#include <ArduinoJson.h>
#include <DHT.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <WiFi.h>
#include <sys/time.h>
#include <time.h>

// ===================== Network settings =====================
// Keep the local AP for service access, but use WiFi STA for MQTT/backend.
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
const char* AP_SSID = "Neurognome_Local";
const char* AP_PASS = "12345678";

const char* MQTT_HOST = "192.168.1.10";
const uint16_t MQTT_PORT = 1883;
const char* MQTT_USER = "esp32";
const char* MQTT_PASS = "CHANGE_ME";
const char* DEVICE_ID = "tray_1";
const char* MQTT_CLIENT_ID = "tray_1";
const char* NTP_SERVER = "pool.ntp.org";

// ===================== MQTT topics =====================
const char* COMMANDS_TOPIC = "farm/tray_1/cmd/#";
const char* CLIMATE_TOPIC = "farm/tray_1/sensors/climate";
const char* WATER_TOPIC = "farm/tray_1/sensors/water";
const char* DEVICE_STATUS_TOPIC = "farm/tray_1/status/devices";
const char* AVAILABILITY_TOPIC = "farm/tray_1/status/availability";

// ===================== Pins =====================
#define DHTPIN 10
#define DHTTYPE DHT22
#define ONE_WIRE_BUS 18

const int HUMIDIFIER_RELAY_PIN = 4;
const int FAN_RELAY_PIN = 5;
const int PUMP_RELAY_PIN = 6;

const int BLUE_PIN = 19;
const int GREEN_PIN = 20;
const int RED_PIN = 21;
const int WHITE_PIN = 16;

// ===================== Runtime settings =====================
const bool RELAY_ACTIVE_LOW = true;
const int LIGHT_MAX_VALUE = 120;
#define PWM_FREQ 5000
#define PWM_RES 8

const unsigned long TELEMETRY_INTERVAL_MS = 2000;
const unsigned long STATUS_INTERVAL_MS = 5000;
const unsigned long WIFI_RECONNECT_INTERVAL_MS = 10000;
const unsigned long MQTT_RECONNECT_INTERVAL_MS = 5000;
const unsigned long DEFAULT_DAY_SCENARIO_TOTAL_MS = 15000;

// ===================== Objects =====================
DHT dht(DHTPIN, DHTTYPE);
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature waterSensor(&oneWire);
WebServer server(80);
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

bool humidifierState = false;
bool pumpState = false;
bool fanState = false;
bool lightState = false;

unsigned long humidifierTimerUntilMs = 0;
unsigned long pumpTimerUntilMs = 0;
unsigned long fanTimerUntilMs = 0;
unsigned long lightTimerUntilMs = 0;

bool dayScenarioScheduled = false;
bool dayScenarioRunning = false;
unsigned long dayScenarioScheduledAtMs = 0;
unsigned long dayScenarioStartedAtMs = 0;
unsigned long dayScenarioTotalMs = DEFAULT_DAY_SCENARIO_TOTAL_MS;
uint64_t dayScenarioStartEpochMs = 0;

unsigned long lastTelemetryAtMs = 0;
unsigned long lastStatusAtMs = 0;
unsigned long lastWifiAttemptAtMs = 0;
unsigned long lastMqttAttemptAtMs = 0;

const int DAY_STAGE_COUNT = 10;

struct RgbwColor {
  int g;
  int r;
  int b;
  int w;
};

// Palette: dawn -> white zenith -> red sunset -> off/night.
RgbwColor dayPalette[DAY_STAGE_COUNT] = {
  {5, 0, 10, 0},
  {40, 30, 10, 20},
  {80, 80, 80, 80},
  {120, 120, 120, 120},
  {120, 120, 120, 120},
  {60, 120, 20, 40},
  {30, 120, 5, 10},
  {5, 120, 0, 5},
  {0, 120, 0, 0},
  {0, 0, 120, 0}
};

bool hasWifiCredentials() {
  return strlen(WIFI_SSID) > 0 && strcmp(WIFI_SSID, "YOUR_WIFI_SSID") != 0;
}

bool timeIsReady() {
  return time(nullptr) > 1700000000;
}

uint64_t nowEpochMs() {
  timeval tv;
  gettimeofday(&tv, nullptr);
  return (uint64_t)tv.tv_sec * 1000ULL + (uint64_t)(tv.tv_usec / 1000ULL);
}

void writeRelayPin(int pin, bool enabled) {
  digitalWrite(pin, RELAY_ACTIVE_LOW ? (enabled ? LOW : HIGH) : (enabled ? HIGH : LOW));
}

void setLightValue(int r, int g, int b, int w) {
  ledcWrite(RED_PIN, g);
  ledcWrite(GREEN_PIN, r);
  ledcWrite(BLUE_PIN, b);
  ledcWrite(WHITE_PIN, w);
}

void stopDayScenario() {
  dayScenarioScheduled = false;
  dayScenarioRunning = false;
  dayScenarioStartEpochMs = 0;
}

int currentDayStage() {
  if (!dayScenarioRunning || dayScenarioTotalMs == 0) {
    return DAY_STAGE_COUNT - 1;
  }

  unsigned long elapsed = millis() - dayScenarioStartedAtMs;
  if (elapsed >= dayScenarioTotalMs) {
    return DAY_STAGE_COUNT - 1;
  }

  float progress = (float)elapsed / (float)dayScenarioTotalMs;
  int stage = (int)(progress * (DAY_STAGE_COUNT - 1));
  if (stage < 0) return 0;
  if (stage >= DAY_STAGE_COUNT) return DAY_STAGE_COUNT - 1;
  return stage;
}

void publishStatus();

void setHumidifier(bool enabled) {
  humidifierState = enabled;
  humidifierTimerUntilMs = 0;
  writeRelayPin(HUMIDIFIER_RELAY_PIN, enabled);
}

void setPump(bool enabled) {
  pumpState = enabled;
  pumpTimerUntilMs = 0;
  writeRelayPin(PUMP_RELAY_PIN, enabled);
}

void setFan(bool enabled) {
  fanState = enabled;
  fanTimerUntilMs = 0;
  writeRelayPin(FAN_RELAY_PIN, enabled);
}

void setLight(bool enabled) {
  lightState = enabled;
  lightTimerUntilMs = 0;
  stopDayScenario();
  if (enabled) {
    setLightValue(LIGHT_MAX_VALUE, LIGHT_MAX_VALUE, LIGHT_MAX_VALUE, LIGHT_MAX_VALUE);
  } else {
    setLightValue(0, 0, 0, 0);
  }
}

void setDeviceState(const String& device, bool enabled) {
  if (device == "humidifier") {
    setHumidifier(enabled);
  } else if (device == "pump") {
    setPump(enabled);
  } else if (device == "fan") {
    setFan(enabled);
  } else if (device == "light") {
    setLight(enabled);
  }
  publishStatus();
}

void setDeviceTimer(const String& device, float seconds) {
  if (seconds <= 0) return;

  unsigned long durationMs = (unsigned long)(seconds * 1000.0f);
  unsigned long untilMs = millis() + durationMs;

  if (device == "humidifier") {
    humidifierState = true;
    humidifierTimerUntilMs = untilMs;
    writeRelayPin(HUMIDIFIER_RELAY_PIN, true);
  } else if (device == "pump") {
    pumpState = true;
    pumpTimerUntilMs = untilMs;
    writeRelayPin(PUMP_RELAY_PIN, true);
  } else if (device == "fan") {
    fanState = true;
    fanTimerUntilMs = untilMs;
    writeRelayPin(FAN_RELAY_PIN, true);
  } else if (device == "light") {
    lightState = true;
    lightTimerUntilMs = untilMs;
    stopDayScenario();
    setLightValue(LIGHT_MAX_VALUE, LIGHT_MAX_VALUE, LIGHT_MAX_VALUE, LIGHT_MAX_VALUE);
  }

  publishStatus();
}

void scheduleDayScenario(uint64_t startAtMs, unsigned long startInMs, unsigned long durationMs) {
  if (durationMs < 1000) {
    durationMs = DEFAULT_DAY_SCENARIO_TOTAL_MS;
  }

  unsigned long delayMs = startInMs;
  if (timeIsReady() && startAtMs > 0) {
    uint64_t nowMs = nowEpochMs();
    delayMs = startAtMs > nowMs ? (unsigned long)(startAtMs - nowMs) : 0;
    if (delayMs > 60000UL) {
      delayMs = startInMs;
    }
  } else if (delayMs == 0) {
    delayMs = 50;
  }

  dayScenarioTotalMs = durationMs;
  dayScenarioStartEpochMs = startAtMs;
  dayScenarioScheduledAtMs = millis() + delayMs;
  dayScenarioScheduled = true;
  dayScenarioRunning = false;
  lightState = true;
  lightTimerUntilMs = 0;

  publishStatus();
}

void startDayScenarioNow(unsigned long durationMs = DEFAULT_DAY_SCENARIO_TOTAL_MS) {
  if (durationMs < 1000) {
    durationMs = DEFAULT_DAY_SCENARIO_TOTAL_MS;
  }

  dayScenarioTotalMs = durationMs;
  dayScenarioScheduled = false;
  dayScenarioRunning = true;
  dayScenarioStartedAtMs = millis();
  dayScenarioStartEpochMs = timeIsReady() ? nowEpochMs() : 0;
  lightState = true;
  publishStatus();
}

void updateDayScenario() {
  if (dayScenarioScheduled && (long)(millis() - dayScenarioScheduledAtMs) >= 0) {
    dayScenarioScheduled = false;
    dayScenarioRunning = true;
    dayScenarioStartedAtMs = millis();
    if (dayScenarioStartEpochMs == 0 && timeIsReady()) {
      dayScenarioStartEpochMs = nowEpochMs();
    }
    publishStatus();
  }

  if (!dayScenarioRunning) return;

  unsigned long elapsed = millis() - dayScenarioStartedAtMs;
  if (elapsed >= dayScenarioTotalMs) {
    dayScenarioRunning = false;
    lightState = false;
    setLightValue(0, 0, 0, 0);
    publishStatus();
    return;
  }

  float progress = (float)elapsed / (float)dayScenarioTotalMs;
  float stageFloat = progress * (DAY_STAGE_COUNT - 1);
  int stageIndex = (int)stageFloat;
  float stageT = stageFloat - stageIndex;

  RgbwColor from = dayPalette[stageIndex];
  RgbwColor to = dayPalette[stageIndex + 1];

  setLightValue(
    from.r + (to.r - from.r) * stageT,
    from.g + (to.g - from.g) * stageT,
    from.b + (to.b - from.b) * stageT,
    from.w + (to.w - from.w) * stageT
  );
}

void updateTimers() {
  unsigned long nowMs = millis();
  bool changed = false;

  if (humidifierTimerUntilMs && (long)(nowMs - humidifierTimerUntilMs) >= 0) {
    setHumidifier(false);
    changed = true;
  }
  if (pumpTimerUntilMs && (long)(nowMs - pumpTimerUntilMs) >= 0) {
    setPump(false);
    changed = true;
  }
  if (fanTimerUntilMs && (long)(nowMs - fanTimerUntilMs) >= 0) {
    setFan(false);
    changed = true;
  }
  if (lightTimerUntilMs && (long)(nowMs - lightTimerUntilMs) >= 0) {
    setLight(false);
    changed = true;
  }

  if (changed) {
    publishStatus();
  }
}

void publishTelemetry() {
  if (!mqtt.connected()) return;

  float airTemp = dht.readTemperature();
  float humidity = dht.readHumidity();
  waterSensor.requestTemperatures();
  float waterTemp = waterSensor.getTempCByIndex(0);

  StaticJsonDocument<128> climateDoc;
  if (!isnan(airTemp)) climateDoc["air_temp"] = airTemp;
  if (!isnan(humidity)) climateDoc["humidity"] = humidity;

  char climatePayload[128];
  serializeJson(climateDoc, climatePayload);
  mqtt.publish(CLIMATE_TOPIC, climatePayload, true);

  StaticJsonDocument<128> waterDoc;
  if (!isnan(waterTemp) && waterTemp > -100.0f) {
    waterDoc["water_temp"] = waterTemp;
  }

  char waterPayload[128];
  serializeJson(waterDoc, waterPayload);
  mqtt.publish(WATER_TOPIC, waterPayload, true);
}

void publishStatus() {
  if (!mqtt.connected()) return;

  StaticJsonDocument<384> doc;
  doc["pump"] = pumpState;
  doc["fan"] = fanState;
  doc["humidifier"] = humidifierState;
  doc["light"] = lightState;
  doc["day_scenario_running"] = dayScenarioRunning || dayScenarioScheduled;
  doc["day_scenario_pending"] = dayScenarioScheduled;
  doc["day_stage"] = currentDayStage();
  doc["day_start_at_ms"] = dayScenarioStartEpochMs;
  doc["day_duration_ms"] = dayScenarioTotalMs;
  doc["uptime_ms"] = millis();

  char payload[384];
  serializeJson(doc, payload);
  mqtt.publish(DEVICE_STATUS_TOPIC, payload, true);
}

void handleTextCommand(const String& device, String command) {
  command.trim();
  command.toUpperCase();

  if (command == "ON") {
    setDeviceState(device, true);
    return;
  }

  if (command == "OFF") {
    setDeviceState(device, false);
    return;
  }

  if (device == "light" && (command == "DAY" || command == "DAY_SCENARIO")) {
    startDayScenarioNow();
    return;
  }

  if (command.startsWith("TIMER ")) {
    float seconds = command.substring(6).toFloat();
    setDeviceTimer(device, seconds);
  }
}

void handleJsonCommand(const String& device, const String& payload) {
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, payload);
  if (error) {
    return;
  }

  String command = doc["command"] | "";
  command.trim();
  command.toUpperCase();

  if (device == "light" && (command == "DAY_SCENARIO" || command == "DAY")) {
    uint64_t startAtMs = doc["start_at_ms"].as<uint64_t>();
    unsigned long startInMs = doc["start_in_ms"] | 0UL;
    unsigned long durationMs = doc["duration_ms"] | DEFAULT_DAY_SCENARIO_TOTAL_MS;
    scheduleDayScenario(startAtMs, startInMs, durationMs);
    return;
  }

  if (command == "ON" || command == "OFF") {
    setDeviceState(device, command == "ON");
    return;
  }

  if (command == "TIMER") {
    float seconds = doc["duration"] | 0.0f;
    setDeviceTimer(device, seconds);
  }
}

String deviceFromTopic(const String& topic) {
  int slash = topic.lastIndexOf('/');
  if (slash < 0 || slash >= topic.length() - 1) {
    return "";
  }
  return topic.substring(slash + 1);
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String topicText = String(topic);
  String body;
  body.reserve(length + 1);
  for (unsigned int i = 0; i < length; i++) {
    body += (char)payload[i];
  }
  body.trim();

  String device = deviceFromTopic(topicText);
  if (device.length() == 0) {
    return;
  }

  if (body.startsWith("{")) {
    handleJsonCommand(device, body);
  } else {
    handleTextCommand(device, body);
  }
}

void maintainWifi() {
  if (!hasWifiCredentials() || WiFi.status() == WL_CONNECTED) {
    return;
  }

  if (millis() - lastWifiAttemptAtMs < WIFI_RECONNECT_INTERVAL_MS) {
    return;
  }

  lastWifiAttemptAtMs = millis();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

void maintainMqtt() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  if (mqtt.connected()) {
    mqtt.loop();
    return;
  }

  if (millis() - lastMqttAttemptAtMs < MQTT_RECONNECT_INTERVAL_MS) {
    return;
  }

  lastMqttAttemptAtMs = millis();
  bool connected = false;
  if (strlen(MQTT_USER) > 0) {
    connected = mqtt.connect(
      MQTT_CLIENT_ID,
      MQTT_USER,
      MQTT_PASS,
      AVAILABILITY_TOPIC,
      0,
      true,
      "offline"
    );
  } else {
    connected = mqtt.connect(MQTT_CLIENT_ID, AVAILABILITY_TOPIC, 0, true, "offline");
  }

  if (connected) {
    mqtt.publish(AVAILABILITY_TOPIC, "online", true);
    mqtt.subscribe(COMMANDS_TOPIC);
    publishStatus();
    publishTelemetry();
  }
}

void handleRoot() {
  float airTemp = dht.readTemperature();
  float humidity = dht.readHumidity();
  waterSensor.requestTemperatures();
  float waterTemp = waterSensor.getTempCByIndex(0);

  String html = "<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Gnome Local</title>";
  html += "<style>body{font-family:sans-serif;text-align:center;padding:20px;background:#f0f2f5}.card{background:white;padding:20px;border-radius:15px;box-shadow:0 4px 6px rgba(0,0,0,.1);margin-bottom:20px}button{padding:15px;width:100%;margin:10px 0;font-size:18px;border:none;color:white;border-radius:8px;cursor:pointer}.on{background:#28a745}.off{background:#dc3545}.info{font-size:18px;color:#333}</style></head><body>";
  html += "<h2>Neurognome ESP32</h2>";
  html += "<div class='card info'><p>Air: " + String(airTemp, 1) + " C | " + String(humidity, 1) + "%</p>";
  html += "<p>Water: " + (isnan(waterTemp) ? "error" : String(waterTemp, 1)) + " C</p>";
  String wifiStatus = WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : String("not connected");
  html += "<p>WiFi: " + wifiStatus + "</p>";
  html += "<p>MQTT: " + String(mqtt.connected() ? "connected" : "offline") + "</p></div>";

  auto drawBtn = [&](String label, String dev, bool state) {
    String cls = state ? "on" : "off";
    return "<a href='/toggle?dev=" + dev + "'><button class='" + cls + "'>" + label + (state ? " ON" : " OFF") + "</button></a>";
  };

  html += "<div class='card'>";
  html += drawBtn("Humidifier", "humidifier", humidifierState);
  html += drawBtn("Pump", "pump", pumpState);
  html += drawBtn("Fan", "fan", fanState);
  html += drawBtn("Light", "light", lightState);
  html += "<br><a href='/day'><button style='background:#6f42c1'>Day scenario (15 sec)</button></a>";
  html += "</div></body></html>";
  server.send(200, "text/html", html);
}

void handleToggle() {
  String dev = server.arg("dev");
  if (dev == "humidifier") {
    setDeviceState("humidifier", !humidifierState);
  } else if (dev == "pump") {
    setDeviceState("pump", !pumpState);
  } else if (dev == "fan") {
    setDeviceState("fan", !fanState);
  } else if (dev == "light") {
    setDeviceState("light", !lightState);
  }

  server.sendHeader("Location", "/");
  server.send(303);
}

void handleDay() {
  startDayScenarioNow();
  server.sendHeader("Location", "/");
  server.send(303);
}

void setupPins() {
  pinMode(HUMIDIFIER_RELAY_PIN, OUTPUT);
  pinMode(PUMP_RELAY_PIN, OUTPUT);
  pinMode(FAN_RELAY_PIN, OUTPUT);

  writeRelayPin(HUMIDIFIER_RELAY_PIN, false);
  writeRelayPin(PUMP_RELAY_PIN, false);
  writeRelayPin(FAN_RELAY_PIN, false);

  ledcAttach(RED_PIN, PWM_FREQ, PWM_RES);
  ledcAttach(GREEN_PIN, PWM_FREQ, PWM_RES);
  ledcAttach(BLUE_PIN, PWM_FREQ, PWM_RES);
  ledcAttach(WHITE_PIN, PWM_FREQ, PWM_RES);
  setLightValue(0, 0, 0, 0);
}

void setupNetwork() {
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(AP_SSID, AP_PASS);

  if (hasWifiCredentials()) {
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    configTime(0, 0, NTP_SERVER);
  }

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  mqtt.setBufferSize(512);
}

void setupWebServer() {
  server.on("/", handleRoot);
  server.on("/toggle", handleToggle);
  server.on("/day", handleDay);
  server.begin();
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  waterSensor.begin();
  setupPins();
  setupNetwork();
  setupWebServer();
}

void loop() {
  server.handleClient();
  maintainWifi();
  maintainMqtt();
  updateTimers();
  updateDayScenario();

  if (mqtt.connected() && millis() - lastTelemetryAtMs >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryAtMs = millis();
    publishTelemetry();
  }

  if (mqtt.connected() && millis() - lastStatusAtMs >= STATUS_INTERVAL_MS) {
    lastStatusAtMs = millis();
    publishStatus();
  }
}
