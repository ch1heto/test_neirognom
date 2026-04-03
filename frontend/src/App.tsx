import { useEffect, useState } from 'react'
import mqtt from 'mqtt'

const MQTT_WS_URL = 'ws://31.56.208.196:9001'
const API_URL = 'http://31.56.208.196:8000/api/device/control'
const CLIMATE_TOPIC = 'farm/tray_1/sensors/climate'
const WATER_TOPIC = 'farm/tray_1/sensors/water'
const SOIL_TOPIC = 'farm/tray_1/sensors/soil'

type CommandState = 'ON' | 'OFF' | 'TIMER'

type ClimateData = {
  air_temp: number
  humidity: number
  lux: number
}

type WaterData = {
  water_temp: number
  distance_cm: number
}

type SoilData = {
  moisture_percent: number
}

type DeviceCardProps = {
  title: string
  deviceType: string
  timerValue: string
  onTimerChange: (value: string) => void
  onCommand: (deviceType: string, state: CommandState, duration?: number) => void
}

function DeviceCard({
  title,
  deviceType,
  timerValue,
  onTimerChange,
  onCommand,
}: DeviceCardProps) {
  const handleTimerStart = () => {
    const duration = Number(timerValue)

    if (!Number.isFinite(duration) || duration <= 0) {
      return
    }

    onCommand(deviceType, 'TIMER', duration)
  }

  return (
    <article className="device-card">
      <div className="device-card__header">
        <h3>{title}</h3>
        <span className="device-card__type">{deviceType}</span>
      </div>

      <div className="device-card__actions">
        <button
          className="control-button control-button--primary"
          onClick={() => onCommand(deviceType, 'ON')}
        >
          Включить
        </button>
        <button
          className="control-button control-button--secondary"
          onClick={() => onCommand(deviceType, 'OFF')}
        >
          Выключить
        </button>
      </div>

      <div className="timer-control">
        <input
          className="timer-control__input"
          type="number"
          step="0.1"
          min="0.1"
          value={timerValue}
          onChange={(event) => onTimerChange(event.target.value)}
          placeholder="0.0"
        />
        <button className="timer-control__button" onClick={handleTimerStart}>
          Запуск (сек)
        </button>
      </div>
    </article>
  )
}

function metricValue(value: number | null, unit: string) {
  return value === null ? '-' : `${value} ${unit}`
}

function App() {
  const [climateData, setClimateData] = useState<ClimateData | null>(null)
  const [waterData, setWaterData] = useState<WaterData | null>(null)
  const [soilData, setSoilData] = useState<SoilData | null>(null)
  const [requestState, setRequestState] = useState('Система готова к управлению')
  const [timerValues, setTimerValues] = useState({
    light: '1.0',
    fan: '1.0',
    pump: '1.0',
    valve: '1.0',
  })

  useEffect(() => {
    const client = mqtt.connect(MQTT_WS_URL)

    client.on('connect', () => {
      client.subscribe([CLIMATE_TOPIC, WATER_TOPIC, SOIL_TOPIC])
    })

    client.on('message', (topic, message) => {
      try {
        const data = JSON.parse(message.toString()) as
          | ClimateData
          | WaterData
          | SoilData

        if (topic === CLIMATE_TOPIC) {
          setClimateData(data as ClimateData)
        }

        if (topic === WATER_TOPIC) {
          setWaterData(data as WaterData)
        }

        if (topic === SOIL_TOPIC) {
          setSoilData(data as SoilData)
        }
      } catch (error) {
        console.error('Не удалось обработать MQTT-сообщение', error)
      }
    })

    client.on('error', (error) => {
      console.error('Ошибка MQTT-подключения', error)
    })

    return () => {
      client.end(true)
    }
  }, [])

  const sendCommand = async (
    deviceType: string,
    state: CommandState,
    duration?: number,
  ) => {
    setRequestState(`Отправка команды ${state} для ${deviceType}`)

    try {
      const payload: {
        target_id: string
        device_type: string
        state: CommandState
        duration?: number
      } = {
        target_id: 'tray_1',
        device_type: deviceType,
        state,
      }

      if (state === 'TIMER' && duration !== undefined) {
        payload.duration = duration
      }

      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      setRequestState(`Команда ${state} для ${deviceType} отправлена`)
    } catch (error) {
      console.error('Не удалось отправить команду устройству', error)
      setRequestState(`Ошибка отправки команды ${state} для ${deviceType}`)
    }
  }

  const setTimerValue = (deviceType: keyof typeof timerValues, value: string) => {
    setTimerValues((current) => ({
      ...current,
      [deviceType]: value,
    }))
  }

  return (
    <main className="dashboard">
      <section className="dashboard__shell">
        <header className="dashboard__header">
          <p className="dashboard__eyebrow">Neuroagronom Platform</p>
          <h1>Панель управления сити-фермой</h1>
          <p className="dashboard__subtitle">
            Телеметрия климата, воды и субстрата, а также управление исполнительными
            устройствами в одном интерфейсе.
          </p>
        </header>

        <section className="dashboard__section">
          <div className="section-heading">
            <h2>Телеметрия</h2>
          </div>

          <div className="telemetry-grid">
            <article className="data-card">
              <h3>Климат</h3>
              <dl className="metric-list">
                <div className="metric-row">
                  <dt>Воздух</dt>
                  <dd>{metricValue(climateData?.air_temp ?? null, '°C')}</dd>
                </div>
                <div className="metric-row">
                  <dt>Влажность</dt>
                  <dd>{metricValue(climateData?.humidity ?? null, '%')}</dd>
                </div>
                <div className="metric-row">
                  <dt>Свет</dt>
                  <dd>{metricValue(climateData?.lux ?? null, 'Lux')}</dd>
                </div>
              </dl>
            </article>

            <article className="data-card">
              <h3>Резервуар</h3>
              <dl className="metric-list">
                <div className="metric-row">
                  <dt>Температура воды</dt>
                  <dd>{metricValue(waterData?.water_temp ?? null, '°C')}</dd>
                </div>
                <div className="metric-row">
                  <dt>Расстояние</dt>
                  <dd>{metricValue(waterData?.distance_cm ?? null, 'см')}</dd>
                </div>
              </dl>
            </article>

            <article className="data-card">
              <h3>Субстрат</h3>
              <dl className="metric-list">
                <div className="metric-row">
                  <dt>Влажность</dt>
                  <dd>{metricValue(soilData?.moisture_percent ?? null, '%')}</dd>
                </div>
              </dl>
            </article>
          </div>
        </section>

        <section className="dashboard__section">
          <div className="section-heading">
            <h2>Управление</h2>
          </div>

          <div className="devices-grid">
            <DeviceCard
              title="Фитосвет"
              deviceType="light"
              timerValue={timerValues.light}
              onTimerChange={(value) => setTimerValue('light', value)}
              onCommand={sendCommand}
            />
            <DeviceCard
              title="Вентиляция"
              deviceType="fan"
              timerValue={timerValues.fan}
              onTimerChange={(value) => setTimerValue('fan', value)}
              onCommand={sendCommand}
            />
            <DeviceCard
              title="Насос"
              deviceType="pump"
              timerValue={timerValues.pump}
              onTimerChange={(value) => setTimerValue('pump', value)}
              onCommand={sendCommand}
            />
            <DeviceCard
              title="Клапан"
              deviceType="valve"
              timerValue={timerValues.valve}
              onTimerChange={(value) => setTimerValue('valve', value)}
              onCommand={sendCommand}
            />
          </div>
        </section>

        <footer className="dashboard__footer">{requestState}</footer>
      </section>
    </main>
  )
}

export default App
