import { useEffect, useRef, useState } from 'react'
import mqtt, { type MqttClient } from 'mqtt'

const IS_LOCAL =
  window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
const MQTT_WS_URL = 'ws://31.56.208.196:9001'
const API_BASE_URL = IS_LOCAL ? 'http://127.0.0.1:8000/api' : 'http://31.56.208.196:8000/api'
const DEVICE_CONTROL_URL = `${API_BASE_URL}/device/control`
const AI_DECIDE_URL = `${API_BASE_URL}/ai/decide`
const AI_LOGS_URL = `${API_BASE_URL}/logs?limit=20`
const CHAT_URL = `${API_BASE_URL}/chat`
const SENSORS_TOPIC = 'farm/tray_1/sensors/#'

type CommandState = 'ON' | 'OFF' | 'TIMER'
type ActiveTab = 'monitoring-ai' | 'manual-control'
type DeviceType = 'pump' | 'light' | 'fan'

type ClimateData = {
  air_temp: number
  humidity: number
}

type WaterData = {
  water_temp: number
}

type AiCommand = {
  device_type: DeviceType
  state: CommandState
  duration?: number
}

type AiLog = {
  id: number
  timestamp: string
  thought: string
  commands_json: string
}

type ChatMessage = {
  role: 'user' | 'assistant'
  text: string
}

type AiDecisionResponse = {
  logs?: string[]
  thought?: string
  commands?: AiCommand[]
}

type ChatResponse = {
  reply?: string
}

type DeviceCardProps = {
  title: string
  deviceType: DeviceType
  timerValue: string
  onTimerChange: (value: string) => void
  onCommand: (deviceType: DeviceType, state: CommandState, duration?: number) => void
}

function metricValue(value: number | null, unit: string) {
  return value === null ? '—' : `${value} ${unit}`
}

function parseCommands(commandsJson: string): AiCommand[] {
  try {
    const parsed = JSON.parse(commandsJson) as unknown
    return Array.isArray(parsed) ? (parsed as AiCommand[]) : []
  } catch {
    return []
  }
}

function formatCommand(command: AiCommand) {
  const deviceTitle: Record<DeviceType, string> = {
    pump: 'Насос',
    light: 'Свет',
    fan: 'Вентилятор',
  }

  if (command.state === 'TIMER' && typeof command.duration === 'number') {
    return `${deviceTitle[command.device_type]}: TIMER ${command.duration} сек.`
  }

  return `${deviceTitle[command.device_type]}: ${command.state}`
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
          step="1"
          min="1"
          value={timerValue}
          onChange={(event) => onTimerChange(event.target.value)}
          placeholder="5"
        />
        <button className="timer-control__button" onClick={handleTimerStart}>
          Включить на время
        </button>
      </div>
    </article>
  )
}

function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('monitoring-ai')
  const [climateData, setClimateData] = useState<ClimateData | null>(null)
  const [waterData, setWaterData] = useState<WaterData | null>(null)
  const [requestState, setRequestState] = useState('Система готова к управлению')
  const [aiLogs, setAiLogs] = useState<AiLog[]>([])
  const [isAiThinking, setIsAiThinking] = useState(false)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      text: 'Нейрогном на связи. Задайте вопрос по состоянию фермы или по моим предыдущим решениям.',
    },
  ])
  const [chatInput, setChatInput] = useState('')
  const [isChatLoading, setIsChatLoading] = useState(false)
  const [timerValues, setTimerValues] = useState<Record<DeviceType, string>>({
    light: '5',
    fan: '5',
    pump: '5',
  })
  const terminalRef = useRef<HTMLDivElement | null>(null)
  const mqttClientRef = useRef<MqttClient | null>(null)

  const loadAiLogs = async () => {
    try {
      const response = await fetch(AI_LOGS_URL)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = (await response.json()) as AiLog[]
      const normalizedLogs = Array.isArray(data) ? [...data].reverse() : []
      setAiLogs(normalizedLogs)
    } catch (error) {
      console.error('Не удалось загрузить журнал Нейрогнома', error)
    }
  }

  useEffect(() => {
    const client = mqtt.connect(MQTT_WS_URL)
    mqttClientRef.current = client

    const onMessageArrived = (topic: string, message: Buffer<ArrayBufferLike>) => {
      try {
        const data = JSON.parse(message.toString()) as ClimateData | WaterData

        if (topic.endsWith('/climate')) {
          setClimateData(data as ClimateData)
        } else if (topic.endsWith('/water')) {
          setWaterData(data as WaterData)
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
      mqttClientRef.current = null
      client.end(true)
    }
  }, [])

  useEffect(() => {
    const handleBodyClick = (event: MouseEvent) => {
      const target = event.target

      if (!(target instanceof HTMLElement)) {
        return
      }

      if (target.closest('button, input, textarea')) {
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
    void loadAiLogs()

    const intervalId = window.setInterval(() => {
      void loadAiLogs()
    }, 15000)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [])

  useEffect(() => {
    if (!terminalRef.current) {
      return
    }

    terminalRef.current.scrollTop = terminalRef.current.scrollHeight
  }, [aiLogs, isAiThinking])

  const sendCommand = async (deviceType: DeviceType, state: CommandState, duration?: number) => {
    setRequestState(`Отправка команды ${state} для устройства ${deviceType}`)

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
          ...(state === 'TIMER' && duration !== undefined
            ? { duration: Number(duration) }
            : {}),
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      setRequestState(`Команда ${state} для устройства ${deviceType} отправлена`)
    } catch (error) {
      console.error('Не удалось отправить команду устройству', error)
      setRequestState(`Ошибка отправки команды ${state} для устройства ${deviceType}`)
    }
  }

  const requestAiDecision = async () => {
    setIsAiThinking(true)

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
      const summary =
        data.thought && data.thought.length > 0
          ? `Нейрогном принял решение: ${data.thought}`
          : 'Нейрогном выполнил запрос без пояснения.'
      setRequestState(summary)
      await loadAiLogs()
    } catch (error) {
      console.error('Не удалось запросить решение Нейрогнома', error)
      const message = error instanceof Error ? error.message : String(error)
      setRequestState(`Ошибка запроса решения Нейрогнома: ${message}`)
    } finally {
      setIsAiThinking(false)
    }
  }

  const askChatQuestion = async (message: string) => {
    const trimmedMessage = message.trim()
    if (!trimmedMessage) {
      return
    }

    setChatMessages((current) => [...current, { role: 'user', text: trimmedMessage }])
    setChatInput('')
    setIsChatLoading(true)

    try {
      const response = await fetch(CHAT_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: trimmedMessage }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = (await response.json()) as ChatResponse
      const reply = data.reply?.trim() || 'Нейрогном не смог сформировать ответ.'
      setChatMessages((current) => [...current, { role: 'assistant', text: reply }])
    } catch (error) {
      const messageText = error instanceof Error ? error.message : String(error)
      setChatMessages((current) => [
        ...current,
        { role: 'assistant', text: `Ошибка связи с Нейрогномом: ${messageText}` },
      ])
    } finally {
      setIsChatLoading(false)
    }
  }

  const setTimerValue = (deviceType: DeviceType, value: string) => {
    setTimerValues((current) => ({
      ...current,
      [deviceType]: value,
    }))
  }

  const publishSimulationMode = (mode: 'HEAT' | 'COLD' | 'NORMAL') => {
    const client = mqttClientRef.current

    if (!client || !client.connected) {
      setRequestState('Ошибка: MQTT-соединение недоступно для отладки симуляции')
      return
    }

    client.publish('farm/sim/control', mode)

    const modeLabel: Record<typeof mode, string> = {
      HEAT: 'жара',
      COLD: 'холод',
      NORMAL: 'нормальный режим',
    }

    setRequestState(`Команда отладки отправлена: ${modeLabel[mode]}`)
  }

  return (
    <main className="dashboard">
      <section className="dashboard__shell">
        <header className="dashboard__header">
          <p className="dashboard__eyebrow">Нейроагроном</p>
          <h1>Панель управления городской фермой</h1>
          <p className="dashboard__subtitle">
            Мониторинг датчиков, журнал решений ИИ и ручное управление исполнительными
            устройствами.
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
              onClick={() => setActiveTab('monitoring-ai')}
              style={{
                background:
                  activeTab === 'monitoring-ai'
                    ? 'linear-gradient(135deg, #1d7f52, #85c66b)'
                    : 'rgba(255, 255, 255, 0.08)',
                color: '#f4ffe9',
                border: '1px solid rgba(133, 198, 107, 0.35)',
                boxShadow:
                  activeTab === 'monitoring-ai'
                    ? '0 12px 30px rgba(18, 78, 48, 0.35)'
                    : 'none',
              }}
            >
              Мониторинг и ИИ
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
              Ручное управление
            </button>
          </div>
        </section>

        {activeTab === 'monitoring-ai' ? (
          <>
            <section className="dashboard__section">
              <div className="section-heading">
                <h2>Показания датчиков</h2>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                  gap: '24px',
                  width: '100%',
                }}
              >
                <article className="sensor-card">
                  <h3>Температура воздуха</h3>
                  <p
                    style={{
                      margin: '12px 0 0',
                      fontSize: '2rem',
                      fontWeight: 700,
                    }}
                  >
                    {metricValue(climateData?.air_temp ?? null, '°C')}
                  </p>
                </article>

                <article className="sensor-card">
                  <h3>Влажность воздуха</h3>
                  <p
                    style={{
                      margin: '12px 0 0',
                      fontSize: '2rem',
                      fontWeight: 700,
                    }}
                  >
                    {metricValue(climateData?.humidity ?? null, '%')}
                  </p>
                </article>

                <article className="sensor-card">
                  <h3>Температура воды</h3>
                  <p
                    style={{
                      margin: '12px 0 0',
                      fontSize: '2rem',
                      fontWeight: 700,
                    }}
                  >
                    {metricValue(waterData?.water_temp ?? null, '°C')}
                  </p>
                </article>
              </div>
            </section>

            <section className="dashboard__section">
              <div className="section-heading">
                <h2>Мысли Нейрогнома</h2>
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
                    <h3 style={{ margin: 0, color: '#d7ffc2' }}>Терминал решений</h3>
                    <p style={{ margin: '6px 0 0', color: 'rgba(208, 255, 185, 0.72)' }}>
                      Последние решения Нейрогнома загружаются автоматически каждые 15 секунд.
                    </p>
                  </div>

                  <button
                    type="button"
                    className="control-button control-button--primary"
                    onClick={requestAiDecision}
                    disabled={isAiThinking}
                    style={{
                      minWidth: '230px',
                      opacity: isAiThinking ? 0.7 : 1,
                      cursor: isAiThinking ? 'wait' : 'pointer',
                    }}
                  >
                    {isAiThinking ? 'Нейрогном думает...' : 'Запросить решение сейчас'}
                  </button>
                </div>

                <div
                  ref={terminalRef}
                  style={{
                    minHeight: '280px',
                    maxHeight: '380px',
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
                  {aiLogs.length === 0 ? (
                    <div style={{ color: 'rgba(157, 255, 176, 0.72)' }}>
                      &gt; Журнал решений пока пуст.
                    </div>
                  ) : null}

                  {aiLogs.map((log) => {
                    const commands = parseCommands(log.commands_json)
                    return (
                      <div
                        key={log.id}
                        style={{
                          marginBottom: '16px',
                          paddingBottom: '16px',
                          borderBottom: '1px solid rgba(120, 255, 170, 0.12)',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          lineHeight: 1.55,
                        }}
                      >
                        <div style={{ color: '#53d97d' }}>&gt; [{log.timestamp}]</div>
                        <div>Мысль: {log.thought || 'Нет пояснения.'}</div>
                        <div>
                          Команды:{' '}
                          {commands.length > 0
                            ? commands.map((command) => formatCommand(command)).join(' | ')
                            : 'действия не требуются'}
                        </div>
                      </div>
                    )
                  })}

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
                      <span>Нейрогном анализирует данные...</span>
                    </div>
                  ) : null}
                </div>
              </div>
            </section>

            <section className="dashboard__section">
              <div className="section-heading">
                <h2>Спросить Нейрогнома</h2>
              </div>

              <div
                className="sensor-card"
                style={{
                  display: 'grid',
                  gap: '18px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    gap: '10px',
                    flexWrap: 'wrap',
                  }}
                >
                  {['Как дела на ферме?', 'Зачем ты включил вентилятор?'].map((example) => (
                    <button
                      key={example}
                      type="button"
                      className="control-button control-button--secondary"
                      onClick={() => void askChatQuestion(example)}
                      disabled={isChatLoading}
                    >
                      {example}
                    </button>
                  ))}
                </div>

                <div
                  style={{
                    display: 'grid',
                    gap: '12px',
                    maxHeight: '320px',
                    overflowY: 'auto',
                    paddingRight: '4px',
                  }}
                >
                  {chatMessages.map((message, index) => (
                    <div
                      key={`${message.role}-${index}`}
                      style={{
                        justifySelf: message.role === 'user' ? 'end' : 'start',
                        maxWidth: '85%',
                        padding: '14px 16px',
                        borderRadius: '18px',
                        background:
                          message.role === 'user'
                            ? 'linear-gradient(135deg, rgba(33, 130, 79, 0.18), rgba(46, 186, 109, 0.22))'
                            : 'rgba(255, 255, 255, 0.06)',
                        border:
                          message.role === 'user'
                            ? '1px solid rgba(133, 198, 107, 0.24)'
                            : '1px solid rgba(255, 255, 255, 0.08)',
                      }}
                    >
                      <strong
                        style={{
                          display: 'block',
                          marginBottom: '6px',
                          color: message.role === 'user' ? '#dfffd0' : '#f4ffe9',
                        }}
                      >
                        {message.role === 'user' ? 'Вы' : 'Нейрогном'}
                      </strong>
                      <span>{message.text}</span>
                    </div>
                  ))}
                </div>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'minmax(0, 1fr) auto',
                    gap: '12px',
                    alignItems: 'end',
                  }}
                >
                  <textarea
                    value={chatInput}
                    onChange={(event) => setChatInput(event.target.value)}
                    placeholder="Например: Почему ты ничего не включил?"
                    rows={3}
                    style={{
                      width: '100%',
                      resize: 'vertical',
                      borderRadius: '18px',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      background: 'rgba(255, 255, 255, 0.05)',
                      color: 'inherit',
                      padding: '14px 16px',
                      font: 'inherit',
                    }}
                  />
                  <button
                    type="button"
                    className="control-button control-button--primary"
                    onClick={() => void askChatQuestion(chatInput)}
                    disabled={isChatLoading}
                    style={{
                      minWidth: '130px',
                      minHeight: '52px',
                    }}
                  >
                    {isChatLoading ? 'Отправка...' : 'Спросить'}
                  </button>
                </div>
              </div>
            </section>
          </>
        ) : (
          <>
            <section className="dashboard__section">
              <div className="section-heading">
                <h2>Ручное управление</h2>
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
                  title="Насос"
                  deviceType="pump"
                  timerValue={timerValues.pump}
                  onTimerChange={(value) => setTimerValue('pump', value)}
                  onCommand={sendCommand}
                />
                <DeviceCard
                  title="Свет"
                  deviceType="light"
                  timerValue={timerValues.light}
                  onTimerChange={(value) => setTimerValue('light', value)}
                  onCommand={sendCommand}
                />
                <DeviceCard
                  title="Вентилятор"
                  deviceType="fan"
                  timerValue={timerValues.fan}
                  onTimerChange={(value) => setTimerValue('fan', value)}
                  onCommand={sendCommand}
                />
              </div>
            </section>

            <section className="dashboard__section">
              <div className="section-heading">
                <h2>Отладка симуляции</h2>
              </div>

              <div
                className="sensor-card"
                style={{
                  display: 'grid',
                  gap: '16px',
                  border: '1px solid rgba(255, 190, 92, 0.18)',
                  background:
                    'linear-gradient(180deg, rgba(52, 30, 10, 0.32), rgba(17, 21, 14, 0.88))',
                }}
              >
                <p style={{ margin: 0, color: 'rgba(255, 236, 201, 0.78)' }}>
                  Панель для переключения тестовых режимов ESP32-симулятора через MQTT.
                </p>

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
                    onClick={() => publishSimulationMode('HEAT')}
                    style={{
                      background: 'linear-gradient(135deg, #8c2218, #ff6b3d)',
                      color: '#fff4ec',
                      border: '1px solid rgba(255, 130, 86, 0.45)',
                      boxShadow: '0 14px 28px rgba(140, 34, 24, 0.28)',
                    }}
                  >
                    Имитировать жару
                  </button>

                  <button
                    type="button"
                    className="control-button"
                    onClick={() => publishSimulationMode('COLD')}
                    style={{
                      background: 'linear-gradient(135deg, #1c466c, #5aa6ff)',
                      color: '#eef7ff',
                      border: '1px solid rgba(112, 178, 255, 0.4)',
                      boxShadow: '0 14px 28px rgba(28, 70, 108, 0.24)',
                    }}
                  >
                    Имитировать холод
                  </button>

                  <button
                    type="button"
                    className="control-button"
                    onClick={() => publishSimulationMode('NORMAL')}
                    style={{
                      background: 'linear-gradient(135deg, #1d7f52, #79c96a)',
                      color: '#f4ffe9',
                      border: '1px solid rgba(133, 198, 107, 0.35)',
                      boxShadow: '0 14px 28px rgba(29, 127, 82, 0.24)',
                    }}
                  >
                    Вернуть в норму
                  </button>
                </div>
              </div>
            </section>
          </>
        )}

        <footer className="dashboard__footer">{requestState}</footer>
      </section>
    </main>
  )
}

export default App
