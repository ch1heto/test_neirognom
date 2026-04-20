import { useEffect, useRef, useState } from 'react'
import mqtt from 'mqtt'

const IS_LOCAL =
  window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
const MQTT_WS_URL = 'ws://31.56.208.196:9001'
const API_BASE_URL = IS_LOCAL ? 'http://127.0.0.1:8000/api' : 'http://31.56.208.196:8000/api'
const DEVICE_CONTROL_URL = `${API_BASE_URL}/device/control`
const AI_DECIDE_URL = `${API_BASE_URL}/ai/decide`
const SENSORS_TOPIC = 'farm/tray_1/sensors/#'

type CommandState = 'ON' | 'OFF' | 'TIMER'
type ActiveTab = 'dashboard-ai' | 'manual-control'

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

type AiDecisionResponse = {
  logs?: string[]
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
  const [activeTab, setActiveTab] = useState<ActiveTab>('dashboard-ai')
  const [climateData, setClimateData] = useState<ClimateData | null>(null)
  const [waterData, setWaterData] = useState<WaterData | null>(null)
  const [soilData, setSoilData] = useState<SoilData | null>(null)
  const [requestState, setRequestState] = useState('Система готова к управлению')
  const [aiLogs, setAiLogs] = useState<string[]>([
    '[boot] AI terminal ready. Waiting for Neurognom.',
  ])
  const [isAiThinking, setIsAiThinking] = useState(false)
  const [timerValues, setTimerValues] = useState({
    light: '1.0',
    fan: '1.0',
    pump: '1.0',
    valve: '1.0',
  })
  const terminalRef = useRef<HTMLDivElement | null>(null)

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

      if (target.closest('button, input')) {
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

  useEffect(() => {
    if (!terminalRef.current) {
      return
    }

    terminalRef.current.scrollTop = terminalRef.current.scrollHeight
  }, [aiLogs, isAiThinking])

  const sendCommand = async (
    device_type: DeviceCardProps['deviceType'],
    state: CommandState,
    duration?: number,
  ) => {
    setRequestState(`Отправка команды ${state} для ${device_type}`)

    try {
      const response = await fetch(DEVICE_CONTROL_URL, {
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

  const askNeurognom = async () => {
    setIsAiThinking(true)
    setAiLogs((current) => [...current, `[${new Date().toLocaleTimeString()}] Asking Neurognom...`])

    try {
      const response = await fetch(AI_DECIDE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = (await response.json()) as AiDecisionResponse
      const nextLogs =
        Array.isArray(data.logs) && data.logs.length > 0
          ? data.logs
          : ['Neurognom returned an empty response.']

      setAiLogs((current) => [...current, ...nextLogs])
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      setAiLogs((current) => [...current, `Network error: ${message}`])
    } finally {
      setIsAiThinking(false)
    }
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

        <section className="dashboard__section" style={{ paddingBottom: 0 }}>
          <div
            style={{
              display: 'flex',
              gap: '12px',
              flexWrap: 'wrap',
            }}
          >
            <button
              type="button"
              className="control-button"
              onClick={() => setActiveTab('dashboard-ai')}
              style={{
                background:
                  activeTab === 'dashboard-ai'
                    ? 'linear-gradient(135deg, #1d7f52, #85c66b)'
                    : 'rgba(255, 255, 255, 0.08)',
                color: '#f4ffe9',
                border: '1px solid rgba(133, 198, 107, 0.35)',
                boxShadow:
                  activeTab === 'dashboard-ai'
                    ? '0 12px 30px rgba(18, 78, 48, 0.35)'
                    : 'none',
              }}
            >
              Dashboard &amp; AI
            </button>
            <button
              type="button"
              className="control-button"
              onClick={() => setActiveTab('manual-control')}
              style={{
                background:
                  activeTab === 'manual-control'
                    ? 'linear-gradient(135deg, #1d7f52, #85c66b)'
                    : 'rgba(255, 255, 255, 0.08)',
                color: '#f4ffe9',
                border: '1px solid rgba(133, 198, 107, 0.35)',
                boxShadow:
                  activeTab === 'manual-control'
                    ? '0 12px 30px rgba(18, 78, 48, 0.35)'
                    : 'none',
              }}
            >
              Manual Control
            </button>
          </div>
        </section>

        {activeTab === 'dashboard-ai' ? (
          <>
            <section className="dashboard__section">
              <div className="section-heading">
                <h2>Телеметрия</h2>
              </div>

              <div
                className="telemetry-grid"
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                  gap: '24px',
                  alignItems: 'start',
                  width: '100%',
                }}
              >
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
                <h2>AI Terminal</h2>
              </div>

              <div
                className="sensor-card"
                style={{
                  padding: '24px',
                  background:
                    'radial-gradient(circle at top, rgba(55, 145, 78, 0.18), rgba(7, 18, 12, 0.96))',
                  border: '1px solid rgba(133, 198, 107, 0.2)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '16px',
                    flexWrap: 'wrap',
                    marginBottom: '18px',
                  }}
                >
                  <div>
                    <h3 style={{ margin: 0, color: '#d7ffc2' }}>Neurognom Console</h3>
                    <p style={{ margin: '6px 0 0', color: 'rgba(208, 255, 185, 0.72)' }}>
                      Локальный агент анализирует последние 15 телеметрических записей.
                    </p>
                  </div>

                  <button
                    type="button"
                    className="control-button control-button--primary"
                    onClick={askNeurognom}
                    disabled={isAiThinking}
                    style={{
                      minWidth: '180px',
                      opacity: isAiThinking ? 0.7 : 1,
                      cursor: isAiThinking ? 'wait' : 'pointer',
                    }}
                  >
                    {isAiThinking ? 'Neurognom online...' : 'Ask Neurognom'}
                  </button>
                </div>

                <div
                  ref={terminalRef}
                  style={{
                    minHeight: '280px',
                    maxHeight: '360px',
                    overflowY: 'auto',
                    padding: '18px',
                    borderRadius: '18px',
                    background:
                      'linear-gradient(180deg, rgba(2, 10, 5, 0.96), rgba(7, 23, 12, 0.96))',
                    border: '1px solid rgba(92, 255, 151, 0.18)',
                    boxShadow:
                      'inset 0 0 0 1px rgba(124, 255, 165, 0.04), inset 0 -24px 48px rgba(0, 0, 0, 0.24)',
                    fontFamily:
                      '"IBM Plex Mono", "Fira Code", "SFMono-Regular", Consolas, monospace',
                    color: '#9dffb0',
                  }}
                >
                  {aiLogs.map((log, index) => (
                    <div
                      key={`${index}-${log}`}
                      style={{
                        marginBottom: '10px',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        lineHeight: 1.55,
                        textShadow: '0 0 10px rgba(100, 255, 150, 0.18)',
                      }}
                    >
                      <span style={{ color: '#53d97d' }}>&gt;</span> {log}
                    </div>
                  ))}

                  {isAiThinking ? (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        color: '#d8ff8d',
                        textShadow: '0 0 14px rgba(223, 255, 109, 0.2)',
                      }}
                    >
                      <span
                        style={{
                          width: '10px',
                          height: '10px',
                          borderRadius: '50%',
                          background: '#c4ff62',
                          boxShadow: '0 0 16px rgba(196, 255, 98, 0.75)',
                          flexShrink: 0,
                        }}
                      />
                      <span>Neurognom is thinking...</span>
                    </div>
                  ) : null}
                </div>
              </div>
            </section>
          </>
        ) : (
          <section className="dashboard__section">
            <div className="section-heading">
              <h2>Управление</h2>
            </div>

            <div
              className="devices-grid"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: '24px',
                alignItems: 'start',
                width: '100%',
              }}
            >
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
        )}

        <footer className="dashboard__footer">{requestState}</footer>
      </section>
    </main>
  )
}

export default App
