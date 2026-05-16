# Нейрогном / Neuroagronomist

![Neuroagronomist](frontend/src/assets/gnome_2.png)

**Нейрогном** — дипломный проект AI-системы для компактной гидропонной сити-фермы. Система собирает телеметрию с ESP32 по MQTT, сохраняет данные в PostgreSQL, показывает состояние фермы в React-интерфейсе и помогает оператору через AI-чат. Backend на FastAPI связывает MQTT, REST API, АгроТехКарты, watchdog-аналитику и публикацию уставок pH/EC для ESP32.

AI-помощник Нейрогном отвечает с учётом активного цикла выращивания, текущих датчиков, pH-настроек, прошлого опыта и краткосрочной истории диалога в браузере. Он даёт рекомендации и объяснения, но не управляет насосами напрямую: backend публикует MQTT-уставки, а реальная ESP32 должна локально выполнять дозирование с safety limits.

## Возможности

- сбор телеметрии по MQTT с ESP32 или локального `sim_esp32.py`;
- активные циклы выращивания по выбранной культуре и лотку;
- АгроТехКарты культур с нормами температуры воздуха, влажности, температуры воды, pH, EC, светового дня и интенсивности света;
- контроль pH/EC, климата, устройств и событий фермы;
- публикация MQTT-уставок pH/EC для ESP32;
- локальное дозирование на ESP32 по уставкам и safety limits;
- AI-чат Нейрогнома с контекстом активного цикла, датчиков, pH-настроек и истории диалога;
- краткосрочное сохранение истории чата в `localStorage` браузера;
- watchdog, события аномалий, рекомендации и журнал системных событий;
- анализ завершённых циклов, обучение на результатах и предложения улучшений АгроТехКарт.

## Архитектура

```text
ESP32 / sim_esp32.py
   ↕ MQTT
MQTT Broker
   ↕
FastAPI Backend ↔ PostgreSQL
   ↕ REST API
React Frontend
```

Поток уставок для дозирования:

```text
Backend → MQTT topic farm/{tray_id}/settings/targets → ESP32 local dosing
```

### ESP32 / sim_esp32.py

- публикует телеметрию климата и воды;
- подписывается на MQTT-команды устройств и target setpoints;
- в реальной прошивке должна локально сравнивать датчики с уставками и выполнять дозирование с safety limits;
- `sim_esp32.py` нужен для локальной проверки без железа и не заменяет аппаратную безопасность.

### MQTT broker

MQTT broker, например Mosquitto, служит транспортом между ESP32/симулятором и backend.

### FastAPI backend

- подписывается на MQTT-телеметрию и статусы;
- сохраняет данные в PostgreSQL;
- отдаёт REST API для frontend;
- публикует target setpoints для ESP32;
- формирует AI-контекст для Нейрогнома;
- запускает watchdog, аналитику, рекомендации и pipeline обучения по завершённым циклам.

### PostgreSQL

Хранит телеметрию, циклы выращивания, АгроТехКарты, события, рекомендации, AI-логи, результаты циклов и предложения улучшений.

### React frontend

- dashboard состояния фермы;
- чат Нейрогнома;
- управление циклами выращивания;
- pH-настройки;
- графики, события, рекомендации и состояние устройств.

## MQTT topics

### Датчики климата

Topic:

```text
farm/tray_1/sensors/climate
```

Payload:

```json
{"air_temp":23.4,"humidity":58.1}
```

### Датчики воды

Topic:

```text
farm/tray_1/sensors/water
```

Payload:

```json
{"water_temp":20.1,"ph":6.2,"ec":1.45}
```

### Уставки для ESP32

Topic:

```text
farm/tray_1/settings/targets
```

Payload:

```json
{
  "tray_id": "tray_1",
  "cycle_id": 13,
  "ph": 5.8,
  "ph_tolerance": 0.2,
  "ec": 1.8,
  "ec_tolerance": 0.1,
  "autodosing_enabled": true,
  "source": "server",
  "updated_at": "2026-05-15T05:07:10"
}
```

Backend публикует этот topic с `retain=True`, поэтому ESP32 может получить последнюю уставку после переподключения.

### Статус pH-дозаторов

```text
farm/tray_1/actuators/ph/status
```

### Ручные команды устройств

```text
farm/tray_1/cmd/pump
farm/tray_1/cmd/light
farm/tray_1/cmd/fan
```

## pH/EC и дозирование

Backend знает активную культуру, день цикла и нормы из активной АгроТехКарты. pH-уставка берётся из пользовательских pH-настроек, а EC-цель вычисляется из нормы EC активной АгроТехКарты.

Backend публикует уставки в MQTT topic `farm/{tray_id}/settings/targets`. ESP32 локально сравнивает свои датчики с уставками, сама решает, какой насос включить, и применяет safety limits: паузы, лимиты доз за час, ограничения длительности и проверки свежести данных. LLM/чат не управляет насосами напрямую и не должен обещать, что насос уже сработал.

Старый сценарий, где сервер напрямую выполняет pH-дозирование как основной режим, больше не является основной архитектурой. Актуальный путь: backend публикует уставки, ESP32 дозирует локально.

## Структура репозитория

```text
.
|-- backend/          # FastAPI, MQTT-клиент, PostgreSQL, AI-контекст, watchdog
|-- frontend/         # React/Vite dashboard и чат Нейрогнома
|-- sim_esp32.py      # локальный симулятор ESP32 для разработки
|-- requirements.txt  # Python-зависимости backend и симулятора
|-- .env.example      # пример переменных окружения
|-- start_farm.bat    # быстрый локальный запуск на Windows
`-- README.md
```

## Требования

- Python 3.11+;
- Node.js и npm;
- PostgreSQL;
- MQTT broker, например Mosquitto;
- доступ к AI API через `POLZA_API_KEY`, если нужен AI-чат и аналитика;
- ESP32 или `sim_esp32.py` для локальной симуляции.

## Настройка `.env`

Создайте `.env` в корне проекта на основе `.env.example`. Не вставляйте реальные секреты в README, git или публичные чаты.

Пример:

```dotenv
DATABASE_URL=postgresql://postgres:password@localhost:5432/neirognom
BROKER_HOST=127.0.0.1
BROKER_PORT=1883
TRAY_ID=tray_1
POLZA_API_KEY=replace_with_your_key
AI_MODEL=gpt-5-nano
POLZA_BASE_URL=https://polza.ai/api/v1/chat/completions
DEV_FEATURES_ENABLED=false
```

В актуальном `.env.example` используются `BROKER_HOST`, `BROKER_PORT`, `DATABASE_URL`, `POLZA_API_KEY`, `AI_MODEL` и `POLZA_BASE_URL`. `TRAY_ID` поддерживается симулятором и по умолчанию равен `tray_1`; `DEV_FEATURES_ENABLED` включает dev-only возможности backend, если они нужны при разработке.

## Локальный запуск

### Установка зависимостей

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

```powershell
cd frontend
npm install
cd ..
```

### Backend

```powershell
cd backend
..\venv\Scripts\activate
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend

```powershell
cd frontend
npm run dev
```

Обычно Vite откроет frontend на `http://localhost:5173` или соседнем свободном порту. `start_farm.bat` запускает frontend на `http://localhost:5174`.

### Симулятор ESP32

```powershell
python sim_esp32.py
```

Симулятор полезен для локальной проверки MQTT, датчиков и получения target setpoints без реального железа. Для аппаратной проверки и продакшен-сценария предпочтительнее реальная ESP32 с локальной логикой дозирования и safety limits.

### Быстрый запуск на Windows

```powershell
start_farm.bat
```

Скрипт поднимает три процесса: `sim_esp32.py`, FastAPI backend и React frontend. Это удобно для разработки, но на сервере вместо симулятора обычно подключается реальная ESP32.

## Серверный запуск

На сервере обычно работают отдельные сервисы:

- `neirognom-backend.service`;
- `nginx`;
- `postgresql`;
- `mosquitto`.

Полезные команды диагностики:

```bash
systemctl status neirognom-backend
systemctl restart neirognom-backend
systemctl status nginx
systemctl status mosquitto
systemctl status postgresql
```

## Полезные API endpoints

- `GET /` — health check backend;
- `GET /api/telemetry` — последние показатели датчиков;
- `POST /api/chat` — чат Нейрогнома;
- `POST /api/cycles/start` — запуск цикла выращивания;
- `GET /api/cycles/current` — текущий активный цикл;
- `GET /api/cycles/current/health` — оценка здоровья активного цикла;
- `GET /api/crops` — список культур;
- `GET /api/ph-target-settings/current` — текущие pH-настройки;
- `PUT /api/ph-target-settings/current` — сохранить pH-настройки;
- `POST /api/targets/publish?tray_id=tray_1` — вручную опубликовать target setpoints;
- `POST /api/device/control` — ручная команда устройству через MQTT;
- `GET /api/ph-dosing/events` — последние события pH-дозирования;
- `GET /api/charts/ph-live` — данные live-графика pH;
- `GET /api/system-feed` — журнал системных событий;
- `GET /api/recommendations/recent` — последние рекомендации.

## Проверка MQTT-уставок

Подпишитесь на topic уставок:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -t 'farm/tray_1/settings/targets' -v
```

В другом терминале попросите backend опубликовать уставки:

```bash
curl -X POST "http://127.0.0.1:8000/api/targets/publish?tray_id=tray_1"
```

Ожидаемо: в MQTT приходит JSON с pH/EC уставками, например `ph`, `ph_tolerance`, `ec`, `ec_tolerance`, `autodosing_enabled`, `source` и `updated_at`.

## Статус проекта

Проект находится в состоянии дипломного прототипа / MVP. Он работает с локальным симулятором и рассчитан на подключение реальной ESP32.

Ключевая идея безопасности: AI объясняет и рекомендует, backend публикует уставки, а дозирование должно выполняться локально на ESP32 с safety limits. Аппаратная прошивка ESP32 остаётся критически важной частью безопасной работы фермы.
