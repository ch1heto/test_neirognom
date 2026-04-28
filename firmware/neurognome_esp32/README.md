# Neurognome ESP32 firmware

Прошивка для реального ESP32-контроллера лотка `tray_1`.

## Библиотеки Arduino

- `PubSubClient`
- `ArduinoJson`
- `DHT sensor library`
- `OneWire`
- `DallasTemperature`

## Настройка перед загрузкой

В `neurognome_esp32.ino` замените:

```cpp
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
const char* MQTT_HOST = "192.168.1.10";
const char* MQTT_USER = "esp32";
const char* MQTT_PASS = "CHANGE_ME";
```

`MQTT_HOST` должен указывать на машину, где запущен MQTT-брокер, тот же адрес используется backend через `BROKER_HOST`.

## MQTT-контракт

Прошивка публикует:

| Топик | Payload |
|---|---|
| `farm/tray_1/sensors/climate` | `{"air_temp":23.4,"humidity":56.0}` |
| `farm/tray_1/sensors/water` | `{"water_temp":20.1}` |
| `farm/tray_1/status/devices` | состояние реле и светового сценария |
| `farm/tray_1/status/availability` | `online` / `offline` |

Прошивка слушает:

| Топик | Payload |
|---|---|
| `farm/tray_1/cmd/pump` | `ON`, `OFF`, `TIMER 10` |
| `farm/tray_1/cmd/fan` | `ON`, `OFF`, `TIMER 10` |
| `farm/tray_1/cmd/humidifier` | `ON`, `OFF`, `TIMER 10` |
| `farm/tray_1/cmd/light` | `ON`, `OFF`, `TIMER 10`, `DAY`, JSON-команда светового дня |

JSON-команда светового дня:

```json
{
  "command": "DAY_SCENARIO",
  "start_at_ms": 1777380000000,
  "start_in_ms": 1200,
  "duration_ms": 15000,
  "stage_count": 10
}
```

ESP32 использует `start_at_ms`, если успела синхронизировать время через NTP. Если времени нет, она стартует через `start_in_ms`. Dashboard получает те же `start_at_ms` и `duration_ms` от backend и считает текущую LED-стадию от этих значений.
