import { type CSSProperties, useEffect, useRef, useState } from 'react'
import mqtt, { type MqttClient } from 'mqtt'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const IS_LOCAL =
  window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
const MQTT_WS_URL = 'ws://31.56.208.196:9001'
const API_BASE_URL = IS_LOCAL ? 'http://127.0.0.1:8000/api' : 'http://31.56.208.196:8000/api'
const DEVICE_CONTROL_URL = `${API_BASE_URL}/device/control`
const AI_LOGS_URL = `${API_BASE_URL}/logs?limit=20`
const SENSORS_TOPIC = 'farm/tray_1/sensors/#'
const HISTORY_LIMIT = 36

type ActiveTab = 'monitor' | 'control'
type CommandState = 'ON' | 'OFF' | 'TIMER'
type DeviceType = 'pump' | 'light' | 'fan'

type ClimateMessage = {
  air_temp?: number
  humidity?: number
}

type AiLog = {
  id: number
  timestamp: string
  thought: string
  commands_json: string
}

type TelemetryPoint = {
  time: string
  temperature: number
  humidity: number
  light: number
}

type DeviceCardProps = {
  title: string
  deviceType: DeviceType
  timerValue: string
  onTimerChange: (value: string) => void
  onSendCommand: (deviceType: DeviceType, state: CommandState, duration?: number) => void
}

const TEXT = {
  appName: 'Нейроагроном',
  title: 'Dashboard Layout Preview',
  subtitle:
    'Темная панель с сохранённой MQTT-логикой, историей телеметрии и подготовленным layout для мониторинга.',
  tabs: {
    monitor: 'Мониторинг',
    control: 'Ручное управление',
  },
  sensors: {
    temperature: 'Температура',
    humidity: 'Влажность',
    light: 'Освещение',
  },
  sections: {
    graph: 'Graph Area',
    thoughts: 'AI Thoughts',
    control: 'Реле и LED',
    simulation: 'Симуляция',
  },
  devices: {
    pump: 'Насос',
    light: 'LED / Свет',
    fan: 'Вентилятор',
  },
  actions: {
    on: 'Включить',
    off: 'Выключить',
    timed: 'На время',
    heat: 'Имитировать жару',
    cold: 'Имитировать холод',
    normal: 'Вернуть норму',
  },
  status: {
    ready: 'Система готова.',
    loadingLogs: 'Не удалось загрузить лог мыслей ИИ',
    mqttError: 'Ошибка MQTT-подключения',
    mqttMessage: 'Не удалось обработать MQTT-сообщение',
    commandError: 'Не удалось отправить команду',
    simulationError: 'MQTT недоступен для симуляции',
    simulationSent: 'Команда симуляции отправлена',
  },
} as const

const panelButtonStyle: CSSProperties = {
  border: '1px solid rgba(255,255,255,0.12)',
  borderRadius: 16,
  background: 'rgba(255,255,255,0.06)',
  color: '#fff',
  padding: '12px 16px',
  cursor: 'pointer',
  transition: 'all 0.25s ease',
  boxShadow: '0 12px 24px rgba(2,6,20,0.18), inset 0 1px 0 rgba(255,255,255,0.1)',
}

const activeTabButtonStyle: CSSProperties = {
  ...panelButtonStyle,
  background: 'rgba(96, 165, 250, 0.18)',
  border: '1px solid rgba(147, 197, 253, 0.28)',
}

const inputStyle: CSSProperties = {
  width: '100%',
  minHeight: 46,
  borderRadius: 14,
  border: '1px solid rgba(255,255,255,0.1)',
  background: 'rgba(255,255,255,0.05)',
  color: '#fff',
  padding: '0 14px',
  outline: 'none',
}

const cardTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: '1rem',
  fontWeight: 700,
}

const glassCardClassName =
  'glass-panel bg-white/[0.03] backdrop-blur-xl border border-white/[0.08] shadow-[inset_0_1px_1px_rgba(255,255,255,0.1)] rounded-[2rem]'

function formatTimeLabel(date = new Date()) {
  return date.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function DeviceCard({
  title,
  deviceType,
  timerValue,
  onTimerChange,
  onSendCommand,
}: DeviceCardProps) {
  const handleTimer = () => {
    const duration = Number(timerValue)

    if (!Number.isFinite(duration) || duration <= 0) {
      return
    }

    onSendCommand(deviceType, 'TIMER', duration)
  }

  return (
    <article
      className={glassCardClassName}
      style={{
        padding: 20,
        display: 'grid',
        gap: 16,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
        <h3 style={cardTitleStyle}>{title}</h3>
        <span style={{ color: 'rgba(148,163,184,0.9)', fontSize: '0.8rem', textTransform: 'uppercase' }}>
          {deviceType}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <button type="button" style={panelButtonStyle} onClick={() => onSendCommand(deviceType, 'ON')}>
          {TEXT.actions.on}
        </button>
        <button type="button" style={panelButtonStyle} onClick={() => onSendCommand(deviceType, 'OFF')}>
          {TEXT.actions.off}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12 }}>
        <input
          type="number"
          min="1"
          step="1"
          value={timerValue}
          onChange={(event) => onTimerChange(event.target.value)}
          style={inputStyle}
          placeholder="5"
        />
        <button type="button" style={panelButtonStyle} onClick={handleTimer}>
          {TEXT.actions.timed}
        </button>
      </div>
    </article>
  )
}

function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('monitor')
  const [temperature, setTemperature] = useState(0)
  const [humidity, setHumidity] = useState(0)
  const [light, setLight] = useState(0)
  const [telemetryHistory, setTelemetryHistory] = useState<TelemetryPoint[]>([])
  const [aiLogs, setAiLogs] = useState<AiLog[]>([])
  const [requestState, setRequestState] = useState<string>(TEXT.status.ready)
  const [timerValues, setTimerValues] = useState<Record<DeviceType, string>>({
    pump: '5',
    light: '5',
    fan: '5',
  })

  const mqttClientRef = useRef<MqttClient | null>(null)
  const thoughtsRef = useRef<HTMLDivElement | null>(null)
  const lightTimerRef = useRef<number | null>(null)
  const lastHistorySignatureRef = useRef('')

  useEffect(() => {
    const loadAiLogs = async () => {
      try {
        const response = await fetch(AI_LOGS_URL)
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const payload = (await response.json()) as AiLog[]
        setAiLogs(Array.isArray(payload) ? [...payload].reverse() : [])
      } catch (error) {
        console.error(TEXT.status.loadingLogs, error)
      }
    }

    void loadAiLogs()
    const intervalId = window.setInterval(() => {
      void loadAiLogs()
    }, 15000)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [])

  useEffect(() => {
    const client = mqtt.connect(MQTT_WS_URL)
    mqttClientRef.current = client

    const handleMessage = (topic: string, message: Buffer<ArrayBufferLike>) => {
      try {
        const payload = JSON.parse(message.toString()) as ClimateMessage

        if (topic.endsWith('/climate')) {
          if (typeof payload.air_temp === 'number') {
            setTemperature(payload.air_temp)
          }

          if (typeof payload.humidity === 'number') {
            setHumidity(payload.humidity)
          }
        }
      } catch (error) {
        console.error(TEXT.status.mqttMessage, error)
      }
    }

    client.on('connect', () => {
      client.subscribe(SENSORS_TOPIC)
    })

    client.on('message', handleMessage)
    client.on('error', (error) => {
      console.error(TEXT.status.mqttError, error)
    })

    return () => {
      mqttClientRef.current = null
      client.end(true)
    }
  }, [])

  useEffect(() => {
    const signature = `${temperature.toFixed(2)}|${humidity.toFixed(2)}|${light.toFixed(2)}`

    if (lastHistorySignatureRef.current === signature) {
      return
    }

    lastHistorySignatureRef.current = signature

    setTelemetryHistory((current) => [
      ...current.slice(-(HISTORY_LIMIT - 1)),
      {
        time: formatTimeLabel(),
        temperature,
        humidity,
        light,
      },
    ])
  }, [temperature, humidity, light])

  useEffect(() => {
    if (!thoughtsRef.current) {
      return
    }

    thoughtsRef.current.scrollTop = thoughtsRef.current.scrollHeight
  }, [aiLogs])

  useEffect(() => {
    return () => {
      if (lightTimerRef.current !== null) {
        window.clearTimeout(lightTimerRef.current)
      }
    }
  }, [])

  const sendCommand = async (deviceType: DeviceType, state: CommandState, duration?: number) => {
    setRequestState(`Отправка ${state} для ${deviceType}`)

    if (deviceType === 'light') {
      if (lightTimerRef.current !== null) {
        window.clearTimeout(lightTimerRef.current)
        lightTimerRef.current = null
      }

      if (state === 'ON') {
        setLight(100)
      } else if (state === 'OFF') {
        setLight(0)
      } else if (state === 'TIMER' && typeof duration === 'number') {
        setLight(100)
        lightTimerRef.current = window.setTimeout(() => {
          setLight(0)
          lightTimerRef.current = null
        }, duration * 1000)
      }
    }

    try {
      const response = await fetch(DEVICE_CONTROL_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          target_id: 'tray_1',
          device_type: deviceType,
          state,
          ...(state === 'TIMER' && typeof duration === 'number' ? { duration } : {}),
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      setRequestState(`Команда ${state} для ${deviceType} отправлена`)
    } catch (error) {
      console.error(TEXT.status.commandError, error)
      setRequestState(TEXT.status.commandError)
    }
  }

  const publishSimulationMode = (mode: 'HEAT' | 'COLD' | 'NORMAL') => {
    const client = mqttClientRef.current

    if (!client || !client.connected) {
      setRequestState(TEXT.status.simulationError)
      return
    }

    client.publish('farm/sim/control', mode)
    setRequestState(`${TEXT.status.simulationSent}: ${mode}`)
  }

  const setTimerValue = (deviceType: DeviceType, nextValue: string) => {
    setTimerValues((current) => ({
      ...current,
      [deviceType]: nextValue,
    }))
  }

  return (
    <main
      className="bg-[#030712] p-8 text-white"
      style={{
        minHeight: '100vh',
        background: '#030712',
        color: '#fff',
      }}
    >
      <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-6">
        <header className="flex flex-col gap-3">
          <p className="m-0 text-xs font-bold uppercase tracking-[0.18em] text-gray-300">
            {TEXT.appName}
          </p>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div className="flex max-w-3xl flex-col gap-2">
              <h1 className="m-0 text-4xl font-semibold leading-tight text-white lg:text-5xl">
                Professional Glass Dashboard
              </h1>
              <p className="m-0 max-w-2xl text-sm leading-7 text-gray-400">
                Monitoring and control surface with preserved MQTT, telemetry, and AI log logic.
              </p>
            </div>

            <div className={`${glassCardClassName} flex items-center gap-4 px-6 py-4`}>
              <div className="flex h-3 w-3 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(74,222,128,0.65)]" />
              <div className="flex flex-col">
                <span className="text-sm font-medium text-white">System Status</span>
                <span className="text-sm text-gray-400">{requestState}</span>
              </div>
            </div>
          </div>
        </header>

        <section className={`${glassCardClassName} flex flex-wrap items-center gap-3 px-4 py-4`}>
          <button
            type="button"
            className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-medium text-white transition hover:border-white/20 hover:bg-white/10"
            style={activeTab === 'monitor' ? activeTabButtonStyle : panelButtonStyle}
            onClick={() => setActiveTab('monitor')}
          >
            Monitoring
          </button>
          <button
            type="button"
            className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-medium text-white transition hover:border-white/20 hover:bg-white/10"
            style={activeTab === 'control' ? activeTabButtonStyle : panelButtonStyle}
            onClick={() => setActiveTab('control')}
          >
            Control
          </button>
        </section>

        {activeTab === 'monitor' ? (
          <section className="grid grid-cols-12 gap-6">
            <div className="col-span-12 grid gap-6 lg:col-span-4">
              <article className={`${glassCardClassName} flex min-h-[220px] flex-col justify-between p-8`}>
                <div className="flex flex-col gap-2">
                  <span className="text-sm uppercase tracking-[0.16em] text-gray-400">Temperature</span>
                  <h2 className="m-0 text-3xl font-semibold text-white">{temperature.toFixed(1)}°C</h2>
                </div>
                <div className="rounded-[1.5rem] border border-white/5 bg-white/[0.02] px-5 py-6 text-sm text-gray-400">
                  Gauge placeholder
                </div>
              </article>

              <article className={`${glassCardClassName} flex min-h-[220px] flex-col justify-between p-8`}>
                <div className="flex flex-col gap-2">
                  <span className="text-sm uppercase tracking-[0.16em] text-gray-400">Humidity</span>
                  <h2 className="m-0 text-3xl font-semibold text-white">{humidity.toFixed(1)}%</h2>
                </div>
                <div className="rounded-[1.5rem] border border-white/5 bg-white/[0.02] px-5 py-6 text-sm text-gray-400">
                  Gauge placeholder
                </div>
              </article>

              <article className={`${glassCardClassName} flex min-h-[220px] flex-col justify-between p-8`}>
                <div className="flex flex-col gap-2">
                  <span className="text-sm uppercase tracking-[0.16em] text-gray-400">Light</span>
                  <h2 className="m-0 text-3xl font-semibold text-white">{light.toFixed(0)}%</h2>
                </div>
                <div className="rounded-[1.5rem] border border-white/5 bg-white/[0.02] px-5 py-6 text-sm text-gray-400">
                  Gauge placeholder
                </div>
              </article>
            </div>

            <div className="col-span-12 grid gap-6 lg:col-span-8">
              <article className={`${glassCardClassName} flex min-h-[420px] flex-col p-8`}>
                <div className="mb-6 flex flex-col gap-2">
                  <span className="text-sm uppercase tracking-[0.16em] text-gray-400">Telemetry Graph</span>
                  <h2 className="m-0 text-2xl font-semibold text-white">AreaChart Overview</h2>
                </div>

                <div className="min-h-0 flex-1 rounded-[1.5rem] border border-white/5 bg-white/[0.02] p-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={telemetryHistory}>
                      <defs>
                        <linearGradient id="telemetryFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#60a5fa" stopOpacity={0.35} />
                          <stop offset="100%" stopColor="#60a5fa" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="4 4" />
                      <XAxis dataKey="time" stroke="#9ca3af" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                      <YAxis stroke="#9ca3af" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{
                          background: 'rgba(3, 7, 18, 0.94)',
                          border: '1px solid rgba(255,255,255,0.08)',
                          borderRadius: 16,
                          color: '#fff',
                        }}
                        labelStyle={{ color: '#d1d5db' }}
                      />
                      <Area
                        type="monotone"
                        dataKey="temperature"
                        stroke="#60a5fa"
                        strokeWidth={3}
                        fill="url(#telemetryFill)"
                        activeDot={{ r: 5, fill: '#60a5fa' }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </article>

              <article className={`${glassCardClassName} flex min-h-[320px] flex-col p-8`}>
                <div className="mb-6 flex flex-col gap-2">
                  <span className="text-sm uppercase tracking-[0.16em] text-gray-400">Terminal</span>
                  <h2 className="m-0 text-2xl font-semibold text-white">AI System Log</h2>
                </div>

                <div
                  ref={thoughtsRef}
                  className="min-h-0 flex-1 overflow-y-auto rounded-[1.5rem] border border-white/5 bg-black/20 p-5 font-mono text-sm leading-7 text-gray-200"
                >
                  {aiLogs.length > 0 ? (
                    <div className="flex flex-col gap-3">
                      {aiLogs.map((log) => (
                        <div key={log.id} className="border-b border-white/5 pb-3 last:border-b-0 last:pb-0">
                          <div className="text-gray-400">[{log.timestamp}]</div>
                          <div className="text-white">{log.thought || 'AI log entry received.'}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-gray-400">Awaiting AI logs...</div>
                  )}
                </div>
              </article>
            </div>
          </section>
        ) : (
          <section className="grid gap-6">
            <div className="grid gap-6 lg:grid-cols-3">
              <DeviceCard
                title={TEXT.devices.pump}
                deviceType="pump"
                timerValue={timerValues.pump}
                onTimerChange={(value) => setTimerValue('pump', value)}
                onSendCommand={sendCommand}
              />
              <DeviceCard
                title={TEXT.devices.light}
                deviceType="light"
                timerValue={timerValues.light}
                onTimerChange={(value) => setTimerValue('light', value)}
                onSendCommand={sendCommand}
              />
              <DeviceCard
                title={TEXT.devices.fan}
                deviceType="fan"
                timerValue={timerValues.fan}
                onTimerChange={(value) => setTimerValue('fan', value)}
                onSendCommand={sendCommand}
              />
            </div>

            <section className={`${glassCardClassName} grid gap-4 p-8`}>
              <div className="flex flex-col gap-2">
                <span className="text-sm uppercase tracking-[0.16em] text-gray-400">Simulation</span>
                <h2 className="m-0 text-2xl font-semibold text-white">MQTT Scenario Controls</h2>
              </div>

              <div className="grid gap-3 lg:grid-cols-3">
                <button type="button" style={panelButtonStyle} onClick={() => publishSimulationMode('HEAT')}>
                  {TEXT.actions.heat}
                </button>
                <button type="button" style={panelButtonStyle} onClick={() => publishSimulationMode('COLD')}>
                  {TEXT.actions.cold}
                </button>
                <button type="button" style={panelButtonStyle} onClick={() => publishSimulationMode('NORMAL')}>
                  {TEXT.actions.normal}
                </button>
              </div>
            </section>
          </section>
        )}
      </div>
    </main>
  )
}

export default App
