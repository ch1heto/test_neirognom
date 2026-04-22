import { useEffect, useMemo, useState } from 'react'
import ChatPanel from './components/ChatPanel'
import DeviceCard from './components/DeviceCard'
import GlassCard from './components/GlassCard'
import HeaderBar from './components/HeaderBar'
import LedTimeline from './components/LedTimeline'
import MetricCard from './components/MetricCard'
import ThoughtStream from './components/ThoughtStream'
import {
  initialDevices,
  initialMessages,
  initialMetrics,
  initialThoughts,
  ledStages,
  sparklineSeries,
} from './data/mock'
import {
  DropletIcon,
  FanIcon,
  HumidityIcon,
  LedIcon,
  LightIcon,
  PumpIcon,
  SlidersIcon,
  ThermometerIcon,
} from './components/Icons'

function formatTime(date = new Date()) {
  return new Intl.DateTimeFormat('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function formatDate(date = new Date()) {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(date)
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

export default function App() {
  const [mode, setMode] = useState('monitoring')
  const [metrics, setMetrics] = useState(initialMetrics)
  const [devices, setDevices] = useState(initialDevices)
  const [thoughts, setThoughts] = useState(initialThoughts)
  const [messages, setMessages] = useState(initialMessages)
  const [chatInput, setChatInput] = useState('')
  const [currentTime, setCurrentTime] = useState(formatTime())
  const [currentDate, setCurrentDate] = useState(formatDate())
  const [activeLedStage, setActiveLedStage] = useState(5)
  const [isLedPlaying, setIsLedPlaying] = useState(false)

  const pushThought = (text) => {
    const item = {
      id: crypto.randomUUID(),
      text,
      time: formatTime(),
    }
    setThoughts((prev) => [item, ...prev].slice(0, 3))
  }

  const pushAssistantMessage = (text) => {
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        from: 'assistant',
        text,
        time: formatTime(),
      },
    ])
  }

  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date()
      setCurrentTime(formatTime(now))
      setCurrentDate(formatDate(now))
    }, 1000)

    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const drift = setInterval(() => {
      setMetrics((prev) => {
        const next = {
          waterTemp: clamp(Number((prev.waterTemp + (Math.random() - 0.5) * 0.14).toFixed(1)), 18.8, 22.4),
          airHumidity: clamp(Math.round(prev.airHumidity + (Math.random() - 0.5) * 2), 60, 75),
          airTemp: clamp(Number((prev.airTemp + (Math.random() - 0.5) * 0.24).toFixed(1)), 21.4, 25.2),
        }

        if (next.airTemp > 24.6) {
          setDevices((current) => ({
            ...current,
            fans: {
              ...current.fans,
              enabled: true,
              level: clamp(current.fans.level + 4, 55, 90),
            },
          }))
          pushThought('Стало чуть жарче. Мягко поднимаю скорость вентиляторов.')
        }

        if (next.airHumidity < 62) {
          pushThought('Влажность просела ниже комфорта. Стоит проверить режим полива.')
        }

        return next
      })
    }, 7000)

    return () => clearInterval(drift)
  }, [])

  useEffect(() => {
    if (!isLedPlaying) return undefined

    const interval = setInterval(() => {
      setActiveLedStage((prev) => {
        const next = prev + 1 > ledStages.length - 1 ? 0 : prev + 1
        setDevices((current) => ({
          ...current,
          led: {
            ...current.led,
            scenario: ledStages[next].label,
          },
        }))
        pushThought(`LED сценарий перешёл на ${ledStages[next].id} — ${ledStages[next].label.toLowerCase()}.`)
        return next
      })
    }, 850)

    const stop = setTimeout(() => setIsLedPlaying(false), 850 * ledStages.length + 250)

    return () => {
      clearInterval(interval)
      clearTimeout(stop)
    }
  }, [isLedPlaying])

  const metricsList = useMemo(
    () => [
      {
        title: 'Температура воды',
        value: metrics.waterTemp,
        unit: '°C',
        norm: '18 – 22 °C',
        color: '#2CB4FF',
        values: sparklineSeries.waterTemp,
        icon: <DropletIcon className="h-6 w-6" />,
      },
      {
        title: 'Влажность воздуха',
        value: metrics.airHumidity,
        unit: '%',
        norm: '60 – 75 %',
        color: '#71F16A',
        values: sparklineSeries.airHumidity,
        icon: <HumidityIcon className="h-6 w-6" />,
      },
      {
        title: 'Температура воздуха',
        value: metrics.airTemp,
        unit: '°C',
        norm: '20 – 25 °C',
        color: '#C668FF',
        values: sparklineSeries.airTemp,
        icon: <ThermometerIcon className="h-6 w-6" />,
      },
    ],
    [metrics],
  )

  const handleToggle = (key) => (enabled) => {
    setDevices((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        enabled,
      },
    }))

    const deviceLabel = {
      fans: 'вентиляторы',
      lights: 'освещение',
      pumps: 'насосы',
    }[key]

    pushThought(`${enabled ? 'Включаю' : 'Выключаю'} ${deviceLabel}.`)
  }

  const handleRange = (key, value) => {
    setDevices((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        level: Number(value),
      },
    }))
  }

  const handleSendMessage = () => {
    const text = chatInput.trim()
    if (!text) return

    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), from: 'user', text, time: formatTime() },
    ])
    setChatInput('')

    const lower = text.toLowerCase()

    setTimeout(() => {
      if (lower.includes('ситуац') || lower.includes('статус') || lower.includes('как дела')) {
        pushAssistantMessage(
          `Сейчас всё стабильно: вода ${metrics.waterTemp} °C, влажность ${metrics.airHumidity}%, воздух ${metrics.airTemp} °C. Вентиляторы ${devices.fans.enabled ? 'включены' : 'выключены'}, LED сценарий — ${devices.led.scenario}.`,
        )
        return
      }

      if (lower.includes('вент')) {
        setDevices((prev) => ({
          ...prev,
          fans: { ...prev.fans, enabled: true, level: 80 },
        }))
        pushThought('Получена команда из чата. Перевожу вентиляторы на 80%.')
        pushAssistantMessage('Готово. Поднял скорость вентиляторов до 80%.')
        return
      }

      if (lower.includes('свет') || lower.includes('led')) {
        setActiveLedStage(5)
        setIsLedPlaying(true)
        pushThought('Перезапускаю дневной LED сценарий по запросу из чата.')
        pushAssistantMessage('Сделано. Включён дневной LED сценарий с плавной последовательностью каналов.')
        return
      }

      if (lower.includes('насос')) {
        setDevices((prev) => ({
          ...prev,
          pumps: { ...prev.pumps, enabled: true, level: 78 },
        }))
        pushAssistantMessage('Насосы активны. Поднял производительность до 78%.')
        return
      }

      pushAssistantMessage(
        'Принял сообщение. Для демо я уже умею отвечать на вопросы о статусе, вентиляторах, насосах и LED сценарии.',
      )
    }, 450)
  }

  const renderMonitoring = () => (
    <div className="grid h-full min-h-0 gap-4 xl:grid-rows-[auto_auto_minmax(0,1fr)]">
      <GlassCard className="rounded-[28px]">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-[22px] font-semibold tracking-tight md:text-[24px]">Мониторинг</div>
            <p className="mt-1.5 text-sm text-white/62">Основные параметры фермы в реальном времени.</p>
          </div>
        </div>
        <div className="mt-4 grid gap-4 xl:grid-cols-3">
          {metricsList.map((item) => (
            <MetricCard key={item.title} {...item} />
          ))}
        </div>
      </GlassCard>

      <GlassCard className="rounded-[28px]">
        <div>
          <div className="text-[22px] font-semibold tracking-tight md:text-[24px]">Устройства</div>
          <p className="mt-1.5 text-sm text-white/62">Полупрозрачные тумблеры и быстрый доступ к ключевым системам.</p>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <DeviceCard
            title={devices.fans.title}
            subtitle={devices.fans.subtitle}
            level={devices.fans.level}
            enabled={devices.fans.enabled}
            onToggle={handleToggle('fans')}
            icon={<FanIcon className="h-6 w-6" />}
            accent="#75F08D"
          />
          <DeviceCard
            title={devices.lights.title}
            subtitle={devices.lights.subtitle}
            level={devices.lights.level}
            enabled={devices.lights.enabled}
            onToggle={handleToggle('lights')}
            icon={<LightIcon className="h-6 w-6" />}
            accent="#FFD667"
          />
          <DeviceCard
            title={devices.pumps.title}
            subtitle={devices.pumps.subtitle}
            level={devices.pumps.level}
            enabled={devices.pumps.enabled}
            onToggle={handleToggle('pumps')}
            icon={<PumpIcon className="h-6 w-6" />}
            accent="#8EC8FF"
          />
          <DeviceCard
            title={devices.led.title}
            subtitle="Сценарий"
            level={100}
            enabled
            onToggle={() => {}}
            icon={<LedIcon className="h-6 w-6" />}
            accent="#D58BFF"
            action={
              <button
                type="button"
                className="shrink-0 rounded-[18px] border border-violet-200/18 bg-violet-400/10 px-4 py-2 text-sm font-medium text-violet-100 transition hover:bg-violet-400/18"
              >
                Настроить
              </button>
            }
          />
        </div>
      </GlassCard>

      <LedTimeline
        stages={ledStages}
        activeIndex={activeLedStage}
        isPlaying={isLedPlaying}
        onPlay={() => setIsLedPlaying(true)}
      />
    </div>
  )

  const renderManual = () => (
    <div className="grid h-full min-h-0 gap-4 xl:grid-rows-[auto_minmax(0,1fr)]">
      <GlassCard className="rounded-[28px]">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/8 text-white/90">
            <SlidersIcon className="h-5 w-5" />
          </div>
          <div>
            <div className="text-[22px] font-semibold tracking-tight md:text-[24px]">Ручное управление</div>
            <p className="mt-1.5 text-sm text-white/62">
              Экран можно связать с реальным API, MQTT или контроллером без переделки структуры.
            </p>
          </div>
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          {[
            {
              key: 'fans',
              label: 'Вентиляторы',
              accent: 'from-emerald-300/90 to-emerald-500/60',
              value: devices.fans.level,
            },
            {
              key: 'lights',
              label: 'Освещение',
              accent: 'from-yellow-300/90 to-orange-400/60',
              value: devices.lights.level,
            },
            {
              key: 'pumps',
              label: 'Насосы',
              accent: 'from-cyan-300/90 to-sky-400/60',
              value: devices.pumps.level,
            },
          ].map((item) => (
            <GlassCard key={item.key} soft className="rounded-[24px]">
              <div className="text-lg font-medium text-white">{item.label}</div>
              <div className="mt-1 text-sm text-white/60">Уровень: {item.value}%</div>
              <input
                type="range"
                min="0"
                max="100"
                value={item.value}
                onChange={(event) => handleRange(item.key, event.target.value)}
                className="mt-4 h-2 w-full cursor-pointer appearance-none rounded-full bg-white/10 accent-white"
              />
              <div className="mt-4 h-2 rounded-full bg-white/8">
                <div className={`h-full rounded-full bg-gradient-to-r ${item.accent}`} style={{ width: `${item.value}%` }} />
              </div>
            </GlassCard>
          ))}
        </div>
      </GlassCard>

      <LedTimeline
        stages={ledStages}
        activeIndex={activeLedStage}
        isPlaying={isLedPlaying}
        onPlay={() => setIsLedPlaying(true)}
        compact
      />
    </div>
  )

  return (
    <div className="farm-shell relative min-h-screen overflow-x-hidden px-3 py-3 md:px-4 md:py-4 xl:h-screen xl:overflow-hidden xl:px-6 xl:py-6">
      <div className="mx-auto flex h-full w-full max-w-[1800px] flex-col gap-4">
        <HeaderBar
          mode={mode}
          setMode={setMode}
          currentTime={currentTime}
          currentDate={currentDate}
        />

        <main className="grid flex-1 gap-4 xl:min-h-0 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="min-h-0">{mode === 'monitoring' ? renderMonitoring() : renderManual()}</div>

          <aside className="grid min-h-0 gap-4 xl:grid-rows-[minmax(0,1fr)_280px]">
            <ChatPanel
              messages={messages}
              input={chatInput}
              onInput={setChatInput}
              onSend={handleSendMessage}
            />
            <ThoughtStream thoughts={thoughts} />
          </aside>
        </main>
      </div>
    </div>
  )
}
