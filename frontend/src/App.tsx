import { useEffect, useState } from 'react'
import mqtt from 'mqtt'

const MQTT_WS_URL = 'ws://31.56.208.196:9001'
const API_URL = 'http://127.0.0.1:8000/api/device/control'
const SENSORS_TOPIC = 'farm/tray_1/sensors/#'

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
  deviceType: 'light' | 'fan' | 'pump' | 'valve'
  timerValue: string
  onTimerChange: (value: string) => void
  onCommand: (deviceType: DeviceCardProps['deviceType'], state: CommandState, duration?: number) => void
}

function metricValue(value: number | null, unit: string) {
  return value === null ? '-' : `${value} ${unit}`
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
          placeholder="1.0"
        />
        <button className="timer-control__button" onClick={handleTimerStart}>
          Включить на время
        </button>
      </div>
    </article>
  )
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

    const onMessageArrived = (topic: string, message: Buffer<ArrayBufferLike>) => {
      try {
        const data = JSON.parse(message.toString()) as
          | ClimateData
          | WaterData
          | SoilData

        if (topic.endsWith('/climate')) {
          setClimateData(data as ClimateData)
        } else if (topic.endsWith('/water')) {
          setWaterData(data as WaterData)
        } else if (topic.endsWith('/soil')) {
          setSoilData(data as SoilData)
        }
      } catch (error) {
        console.error('Не удалось обработать MQTT-сообщение', error)
      }
    }

    client.on('connect', () => {
      client.subscribe(SENSORS_TOPIC)
    })

    client.on('message', onMessageArrived)
    client.on('error', (error) => {
      console.error('Ошибка MQTT-подключения', error)
    })

    return () => {
      client.end(true)
    }
  }, [])

  useEffect(() => {
    const handleBodyClick = (event: MouseEvent) => {
      const target = event.target

      if (!(target instanceof HTMLElement)) {
        return
      }

      if (target.closest('.dashboard__shell')) {
        return
      }

      const leavesCount = Math.floor(Math.random() * 2) + 3

      for (let index = 0; index < leavesCount; index += 1) {
        const leaf = document.createElement('div')
        const size = 10 + Math.random() * 10
        const offsetX = (Math.random() - 0.5) * 36
        const duration = 1600 + Math.random() * 900
        const drift = `${(Math.random() - 0.5) * 90}px`
        const rotation = `${(Math.random() - 0.5) * 120}deg`

        leaf.className = 'leaf'
        leaf.style.left = `${event.clientX + offsetX}px`
        leaf.style.top = `${event.clientY - 8}px`
        leaf.style.width = `${size}px`
        leaf.style.height = `${size * 0.72}px`
        leaf.style.setProperty('--leaf-drift', drift)
        leaf.style.setProperty('--leaf-rotate', rotation)
        leaf.style.setProperty('--leaf-duration', `${duration}ms`)

        leaf.addEventListener('animationend', () => {
          leaf.remove()
        })

        document.body.appendChild(leaf)
      }
    }

    document.body.addEventListener('click', handleBodyClick)

    return () => {
      document.body.removeEventListener('click', handleBodyClick)
      document.querySelectorAll('.leaf').forEach((leaf) => leaf.remove())
    }
  }, [])

  const sendCommand = async (
    device_type: DeviceCardProps['deviceType'],
    state: CommandState,
    duration?: number,
  ) => {
    setRequestState(`Отправка команды ${state} для ${device_type}`)

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          target_id: 'tray_1',
          device_type,
          state,
          ...(state === 'TIMER' && duration !== undefined
            ? { duration: Number(duration) }
            : {}),
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      setRequestState(`Команда ${state} для ${device_type} отправлена`)
    } catch (error) {
      console.error('Не удалось отправить команду устройству', error)
      setRequestState(`Ошибка отправки команды ${state} для ${device_type}`)
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
            Телеметрия и управление исполнительными устройствами в едином интерфейсе.
          </p>
        </header>

        <section className="dashboard__section">
          <div className="section-heading">
            <h2>Телеметрия</h2>
          </div>

          <div className="telemetry-grid">
            <article className="sensor-card">
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

            <article className="sensor-card">
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

            <article className="sensor-card">
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
