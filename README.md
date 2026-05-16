# Нейрогном / Neuroagronomist

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Frontend-61DAFB?style=flat&logo=react&logoColor=111111)
![Vite](https://img.shields.io/badge/Vite-Bundler-646CFF?style=flat&logo=vite&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=flat&logo=postgresql&logoColor=white)
![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?style=flat&logo=eclipsemosquitto&logoColor=white)
![ESP32](https://img.shields.io/badge/ESP32-Device-000000?style=flat&logo=espressif&logoColor=white)
![Nginx](https://img.shields.io/badge/Nginx-Proxy-009639?style=flat&logo=nginx&logoColor=white)

AI-система для компактной гидропонной сити-фермы: собирает телеметрию по MQTT, ведёт циклы выращивания, оценивает pH/EC и климат по АгроТехКартам, а Нейрогном объясняет состояние фермы в чате.

![Neuroagronomist](frontend/src/assets/gnome_2.png)

## Навигация

- [Возможности](#возможности)
- [Что умеет Нейрогном](#что-умеет-нейрогном)
- [Архитектура](#архитектура)
- [MQTT topics](#mqtt-topics)
- [pH/EC и дозирование](#phec-и-дозирование)
- [Структура проекта](#структура-проекта)
- [Запуск](#запуск)
- [API](#api)
- [Проверка уставок](#проверка-уставок)
- [Статус](#статус)

## Возможности

- MQTT-телеметрия климата и воды с ESP32 или `sim_esp32.py`.
- Активные циклы выращивания по выбранной культуре.
- АгроТехКарты с нормами pH, EC, климата и света.
- Dashboard состояния фермы, устройств, pH/EC, событий и графиков.
- AI-чат Нейрогнома с контекстом цикла, датчиков, pH-настроек и истории диалога.
- Краткосрочная история чата в `localStorage` браузера.
- Watchdog, аномалии, рекомендации и системный журнал.
- Анализ завершённых циклов и предложения улучшений АгроТехКарт.
- Retained MQTT target setpoints для ESP32.
- Локальное дозирование на ESP32 с safety limits.

## Что умеет Нейрогном

| Модуль | Что делает |
|---|---|
| ESP32 | Отправляет датчики и принимает уставки |
| Backend | Хранит данные, оценивает нормы, публикует MQTT target setpoints |
| Frontend | Показывает dashboard, циклы, pH/EC и чат |
| AI | Объясняет состояние фермы и помогает оператору |
| PostgreSQL | Хранит телеметрию, циклы, карты, события |

## Архитектура

```mermaid
flowchart LR
  ESP32[ESP32 / sim_esp32.py] <-- MQTT --> MQTT[MQTT Broker]
  MQTT <-- MQTT --> API[FastAPI Backend]
  API <-- SQL --> DB[(PostgreSQL)]
  UI[React Frontend] <-- REST API --> API
  API --> TARGETS[MQTT target setpoints]
  TARGETS --> ESP32
```

```text
Backend → MQTT topic farm/{tray_id}/settings/targets → ESP32 local dosing
```

| Компонент | Роль |
|---|---|
| ESP32 / `sim_esp32.py` | Публикует датчики, принимает команды и уставки |
| MQTT broker | Транспорт между ESP32, симулятором и backend |
| FastAPI backend | REST API, MQTT-клиент, AI-контекст, watchdog, target setpoints |
| PostgreSQL | Хранилище телеметрии, циклов, карт, событий и рекомендаций |
| React frontend | Dashboard, чат, циклы, pH-настройки, графики и события |

## MQTT topics

| Направление | Topic | Назначение |
|---|---|---|
| ESP32 → Backend | `farm/tray_1/sensors/climate` | Температура и влажность воздуха |
| ESP32 → Backend | `farm/tray_1/sensors/water` | Температура воды, pH, EC |
| Backend → ESP32 | `farm/tray_1/settings/targets` | Уставки pH/EC |
| ESP32 → Backend | `farm/tray_1/actuators/ph/status` | Статус pH-дозаторов |
| Backend → ESP32 | `farm/tray_1/cmd/#` | Ручные команды устройств |

### Payload датчиков

```json
{"air_temp":23.4,"humidity":58.1}
```

```json
{"water_temp":20.1,"ph":6.2,"ec":1.45}
```

### Payload уставок

Topic уставок:

```text
farm/{tray_id}/settings/targets
```

Пример:

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

Backend публикует уставки с `retain=True`, поэтому ESP32 может получить последнее значение после переподключения.

## pH/EC и дозирование

Backend знает активную культуру, день цикла и нормы из активной АгроТехКарты. pH берётся из пользовательских pH-настроек, EC берётся из нормы активной АгроТехКарты.

Актуальный сценарий:

1. Backend оценивает активный цикл и формирует target setpoints.
2. Backend публикует retained MQTT-уставки в `farm/{tray_id}/settings/targets`.
3. ESP32 локально сравнивает свои датчики с уставками.
4. ESP32 сама дозирует с safety limits.
5. AI-чат объясняет состояние и помогает оператору, но не включает насосы напрямую.

Это разделяет ответственность: backend знает контекст фермы, ESP32 отвечает за физическое действие, safety limits и локальную защиту.

## Структура проекта

```text
.
|-- backend/          # FastAPI, MQTT, PostgreSQL, AI-контекст, watchdog
|-- frontend/         # React/Vite dashboard и чат
|-- sim_esp32.py      # локальная симуляция ESP32 без железа
|-- requirements.txt  # Python-зависимости
|-- .env.example      # пример переменных окружения
|-- start_farm.bat    # быстрый запуск на Windows
`-- README.md
```

## Требования

| Зависимость | Для чего нужна |
|---|---|
| Python 3.11+ | Backend и симулятор |
| Node.js / npm | Frontend |
| PostgreSQL | Основная база данных |
| Mosquitto или другой MQTT broker | MQTT-транспорт |
| `POLZA_API_KEY` | AI-чат и аналитика |
| ESP32 или `sim_esp32.py` | Датчики и локальная проверка |

## Настройка `.env`

Создайте `.env` в корне проекта на основе `.env.example`.

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

`TRAY_ID` используется симулятором и по умолчанию равен `tray_1`. `DEV_FEATURES_ENABLED` нужен только для dev-only возможностей backend.

## Запуск

### Установка

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

### Симулятор ESP32

```powershell
python sim_esp32.py
```

### Быстрый старт на Windows

```powershell
start_farm.bat
```

`start_farm.bat` поднимает симулятор, backend и frontend в отдельных терминалах. Для аппаратной проверки вместо симулятора подключается реальная ESP32.

## Сервер

На сервере обычно работают:

| Сервис | Назначение |
|---|---|
| `neirognom-backend.service` | FastAPI backend |
| `nginx` | Reverse proxy |
| `postgresql` | База данных |
| `mosquitto` | MQTT broker |

```bash
systemctl status neirognom-backend
systemctl restart neirognom-backend
systemctl status nginx
systemctl status mosquitto
systemctl status postgresql
```

## API

| Endpoint | Назначение |
|---|---|
| `GET /` | Health check backend |
| `GET /api/telemetry` | Последние показатели датчиков |
| `POST /api/chat` | Чат Нейрогнома |
| `POST /api/cycles/start` | Запуск цикла выращивания |
| `GET /api/cycles/current` | Текущий активный цикл |
| `GET /api/cycles/current/health` | Оценка активного цикла |
| `GET /api/crops` | Список культур |
| `GET /api/ph-target-settings/current` | Текущие pH-настройки |
| `PUT /api/ph-target-settings/current` | Сохранение pH-настроек |
| `POST /api/targets/publish?tray_id=tray_1` | Публикация target setpoints |
| `POST /api/device/control` | Ручная команда устройству |
| `GET /api/ph-dosing/events` | События pH-дозирования |
| `GET /api/charts/ph-live` | Live-график pH |
| `GET /api/system-feed` | Системный журнал |
| `GET /api/recommendations/recent` | Последние рекомендации |

## Проверка уставок

Подписка на retained topic:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -t 'farm/tray_1/settings/targets' -v
```

Публикация уставок через backend:

```bash
curl -X POST "http://127.0.0.1:8000/api/targets/publish?tray_id=tray_1"
```

Ожидаемый результат – в MQTT приходит JSON с `ph`, `ph_tolerance`, `ec`, `ec_tolerance`, `autodosing_enabled`, `source` и `updated_at`.

## Статус

Нейрогном находится в состоянии **MVP / prototype**. Проект работает с локальным симулятором и рассчитан на реальную ESP32 в рабочей схеме.

AI помогает оператору понимать состояние фермы, backend публикует MQTT-уставки, а физическое дозирование должно выполняться локально на ESP32 с safety limits.
