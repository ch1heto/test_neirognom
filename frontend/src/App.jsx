import { useEffect, useMemo, useState } from 'react'
import ChatPanel from './components/ChatPanel'
import DeviceCard from './components/DeviceCard'
import GlassCard from './components/GlassCard'
import HeaderBar from './components/HeaderBar'
import LedTimeline from './components/LedTimeline'
import MetricCard from './components/MetricCard'
import ThoughtStream from './components/ThoughtStream'
import {
  initialMetrics,
  ledStages,
  sparklineSeries,
} from './data/mock'
import {
  DropletIcon,
  EcIcon,
  FanIcon,
  HumidityIcon,
  LightIcon,
  PhIcon,
  PlayIcon,
  PumpIcon,
  SlidersIcon,
  ThermometerIcon,
} from './components/Icons'
import arugulaImage from './assets/crops/arugula.webp'
import basilImage from './assets/crops/basil.webp'
import cilantroImage from './assets/crops/cilantro.webp'
import dillImage from './assets/crops/dill.webp'
import lettuceImage from './assets/crops/lettuce.webp'
import mangoldImage from './assets/crops/mangold.webp'
import mintImage from './assets/crops/mint.webp'
import pakChoiImage from './assets/crops/pak_choi.webp'
import parsleyImage from './assets/crops/parsley.webp'
import spinachImage from './assets/crops/spinach.webp'

const API_BASE_URL =
  window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : `${window.location.protocol}//${window.location.hostname}:8000`
const TELEMETRY_POLL_INTERVAL_MS = 2000
const LOGS_POLL_INTERVAL_MS = 5000
const DEFAULT_TRAY_ID = 'tray_1'

const FALLBACK_CROPS = [
  { slug: 'basil', name_ru: 'Базилик', crop_type: 'herb', version_label: 'v1.0' },
  { slug: 'lettuce', name_ru: 'Салат', crop_type: 'leafy', version_label: 'v1.0' },
  { slug: 'arugula', name_ru: 'Руккола', crop_type: 'leafy', version_label: 'v1.0' },
  { slug: 'spinach', name_ru: 'Шпинат', crop_type: 'leafy', version_label: 'v1.0' },
  { slug: 'cilantro', name_ru: 'Кинза', crop_type: 'herb', version_label: 'v1.0' },
  { slug: 'mangold', name_ru: 'Мангольд', crop_type: 'leafy', version_label: 'v1.0' },
  { slug: 'dill', name_ru: 'Укроп', crop_type: 'herb', version_label: 'v1.0' },
  { slug: 'mint', name_ru: 'Мята', crop_type: 'herb', version_label: 'v1.0' },
  { slug: 'pak_choi', name_ru: 'Пак-чой', crop_type: 'leafy', version_label: 'v1.0' },
  { slug: 'parsley', name_ru: 'Петрушка', crop_type: 'herb', version_label: 'v1.0' },
]

const CROP_VISUALS = {
  basil: { label: 'Базилик', image: basilImage, gradient: 'from-emerald-300/24 via-green-500/14 to-emerald-950/20' },
  lettuce: { label: 'Салат', image: lettuceImage, gradient: 'from-lime-300/22 via-green-500/12 to-slate-900/20' },
  arugula: { label: 'Руккола', image: arugulaImage, gradient: 'from-green-300/18 via-emerald-500/12 to-slate-900/20' },
  spinach: { label: 'Шпинат', image: spinachImage, gradient: 'from-green-300/20 via-emerald-500/12 to-slate-950/20' },
  cilantro: { label: 'Кинза', image: cilantroImage, gradient: 'from-emerald-200/20 via-lime-500/12 to-slate-950/20' },
  chard: { label: 'Мангольд', image: mangoldImage, gradient: 'from-rose-300/16 via-emerald-400/12 to-slate-950/20' },
  mangold: { label: 'Мангольд', image: mangoldImage, gradient: 'from-rose-300/16 via-emerald-400/12 to-slate-950/20' },
  dill: { label: 'Укроп', image: dillImage, gradient: 'from-green-200/18 via-lime-500/12 to-slate-950/20' },
  mint: { label: 'Мята', image: mintImage, gradient: 'from-cyan-200/16 via-emerald-400/12 to-slate-950/20' },
  pak_choi: { label: 'Пак-чой', image: pakChoiImage, gradient: 'from-lime-200/18 via-green-500/12 to-slate-950/20' },
  parsley: { label: 'Петрушка', image: parsleyImage, gradient: 'from-emerald-200/16 via-green-500/12 to-slate-950/20' },
}

const CHAT_THINKING_STEPS = [
  'Получен запрос пользователя',
  'Анализирую смысл сообщения',
  'Определяю нужный контекст',
  'Проверяю доступные данные фермы',
  'Сверяю показатели с нормами',
  'Формирую ответ Нейрогнома',
]

function makeId() {
  if (window.crypto && typeof window.crypto.randomUUID === 'function') {
    return window.crypto.randomUUID()
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

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

function formatTimestampLabel(timestamp) {
  if (!timestamp || typeof timestamp !== 'string') {
    return formatTime()
  }

  if (timestamp.length >= 16) {
    return timestamp.slice(11, 16)
  }

  return timestamp
}

function toNumberOrFallback(value, fallback) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function toNumberOrNull(value) {
  if (value === null || value === undefined) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function formatMetricValue(value, digits) {
  if (value === null || value === undefined) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : null
}

function buildChatHistory(messages, userMessage) {
  return [...messages, userMessage].map((message) => ({
    role: message.from === 'assistant' ? 'assistant' : 'user',
    content: message.text,
  }))
}

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  if (!response.ok) {
    let detail = null
    try {
      detail = await response.json()
    } catch {
      detail = null
    }
    const error = new Error(`Request failed with status ${response.status}`)
    error.status = response.status
    error.detail = detail
    throw error
  }

  return response.json()
}

function parseLogMeta(entry) {
  try {
    if (!entry?.commands_json) return null

    if (typeof entry.commands_json === 'string') {
      return JSON.parse(entry.commands_json)
    }

    return entry.commands_json
  } catch {
    return null
  }
}

function getCropLabel(crop) {
  if (!crop) return 'Культура'
  return crop.name_ru || crop.crop_name_ru || CROP_VISUALS[crop.slug]?.label || crop.slug
}

function normalizeCrop(crop) {
  const slug = crop.slug || crop.crop_slug
  return {
    ...crop,
    slug,
    name_ru: crop.name_ru || crop.crop_name_ru || CROP_VISUALS[slug]?.label || slug,
    version_label: crop.version_label || 'v1.0',
  }
}

function getCropVisual(slug) {
  return CROP_VISUALS[slug] || {
    label: slug,
    emoji: (slug || '?').slice(0, 1).toUpperCase(),
    gradient: 'from-emerald-300/18 via-slate-400/10 to-slate-950/20',
  }
}

function getErrorMessage(error, fallback) {
  if (typeof error?.detail?.detail?.error === 'string') return error.detail.detail.error
  if (typeof error?.detail?.error === 'string') return error.detail.error
  return fallback
}

export default function App() {
  const [mode, setMode] = useState('monitoring')
  const [metrics, setMetrics] = useState(initialMetrics)
  const [devices, setDevices] = useState({
    fans: { title: 'Вентиляция', subtitle: 'Обдув', level: 0, enabled: false },
    lights: { title: 'Освещение', subtitle: 'Фитолампы', level: 0, enabled: false },
    pumps: { title: 'Полив', subtitle: 'Насосы', level: 0, enabled: false },
    led: { title: 'LED', scenario: 'Ожидание' }
  })
  const [thoughts, setThoughts] = useState([])
  const [messages, setMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [isChatThinking, setIsChatThinking] = useState(false)
  const [currentTime, setCurrentTime] = useState(formatTime())
  const [currentDate, setCurrentDate] = useState(formatDate())
  const [activeLedStage, setActiveLedStage] = useState(5)
  const [isLedPlaying, setIsLedPlaying] = useState(false)
  const [crops, setCrops] = useState(FALLBACK_CROPS)
  const [selectedCropSlug, setSelectedCropSlug] = useState('basil')
  const [currentCycle, setCurrentCycle] = useState(null)
  const [isCycleLoading, setIsCycleLoading] = useState(false)
  const [cycleError, setCycleError] = useState('')

  const pushThought = (text) => {
    const item = {
      id: makeId(),
      text,
      time: formatTime(),
    }
    setThoughts((prev) => [item, ...prev].slice(0, 5))
  }

  const pushAssistantMessage = (text) => {
    setMessages((prev) => [
      ...prev,
      {
        id: makeId(),
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
    let isMounted = true

    const loadTelemetry = async () => {
      try {
        const data = await requestJson('/api/telemetry')
        if (!isMounted) return

        setMetrics((prev) => ({
          waterTemp: toNumberOrFallback(data.water_temp, prev.waterTemp),
          airHumidity: toNumberOrFallback(data.humidity, prev.airHumidity),
          airTemp: toNumberOrFallback(data.air_temp, prev.airTemp),
          ph: toNumberOrNull(data.ph),
          ec: toNumberOrNull(data.ec),
        }))
      } catch (error) {
        console.error('Failed to load telemetry', error)
      }
    }

    loadTelemetry()
    const telemetryPoller = setInterval(loadTelemetry, TELEMETRY_POLL_INTERVAL_MS)

    return () => {
      isMounted = false
      clearInterval(telemetryPoller)
    }
  }, [])

  useEffect(() => {
    let isMounted = true

    const loadThoughts = async () => {
      try {
        const data = await requestJson('/api/logs?limit=5')
        if (!isMounted || !Array.isArray(data)) return

        setThoughts((prev) => {
          const serverLogs = data
            .filter((entry) => {
              const meta = parseLogMeta(entry)
              return meta?.type !== 'chat'
            })
            .map((entry) => ({
              id: `log-${entry.id ?? makeId()}`,
              text: entry.thought || 'Нет записанной мысли.',
              time: formatTimestampLabel(entry.timestamp),
            }))

          const serverIds = new Set(serverLogs.map((log) => log.id))

          const localLogs = prev.filter(
            (log) => !serverIds.has(log.id) && !log.id.startsWith('log-')
          )

          return [...localLogs, ...serverLogs].slice(0, 15)
        })
      } catch (error) {
        console.error('Failed to load AI logs', error)
      }
    }

    loadThoughts()
    const logsPoller = setInterval(loadThoughts, LOGS_POLL_INTERVAL_MS)

    return () => {
      isMounted = false
      clearInterval(logsPoller)
    }
  }, [])

  const loadCurrentCycle = async () => {
    const data = await requestJson(`/api/cycles/current?tray_id=${DEFAULT_TRAY_ID}`)
    setCurrentCycle(data || null)
    return data
  }

  useEffect(() => {
    let isMounted = true

    const loadCycleData = async () => {
      setIsCycleLoading(true)
      try {
        const [cropsData, cycleData] = await Promise.all([
          requestJson('/api/crops'),
          requestJson(`/api/cycles/current?tray_id=${DEFAULT_TRAY_ID}`),
        ])

        if (!isMounted) return

        const normalizedCrops = Array.isArray(cropsData) && cropsData.length
          ? cropsData.map(normalizeCrop)
          : FALLBACK_CROPS
        setCrops(normalizedCrops)
        setSelectedCropSlug((prev) => (
          normalizedCrops.some((crop) => crop.slug === prev) ? prev : normalizedCrops[0]?.slug || 'basil'
        ))
        setCurrentCycle(cycleData || null)
        setCycleError('')
      } catch (error) {
        console.error('Failed to load cycle data', error)
        if (!isMounted) return

        setCrops(FALLBACK_CROPS)
        setSelectedCropSlug((prev) => prev || FALLBACK_CROPS[0].slug)
        setCycleError('Не удалось загрузить данные цикла. Показаны доступные культуры по умолчанию.')
      } finally {
        if (isMounted) setIsCycleLoading(false)
      }
    }

    loadCycleData()

    return () => {
      isMounted = false
    }
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
        value: formatMetricValue(metrics.waterTemp, 1),
        unit: '°C',
        norm: '18 – 22 °C',
        color: '#2CB4FF',
        values: sparklineSeries.waterTemp,
        icon: <DropletIcon className="h-6 w-6" />,
      },
      {
        title: 'Влажность воздуха',
        value: formatMetricValue(metrics.airHumidity, 1),
        unit: '%',
        norm: '52 – 60 %',
        color: '#71F16A',
        values: sparklineSeries.airHumidity,
        icon: <HumidityIcon className="h-6 w-6" />,
      },
      {
        title: 'Температура воздуха',
        value: formatMetricValue(metrics.airTemp, 1),
        unit: '°C',
        norm: '20 – 25 °C',
        color: '#C668FF',
        values: sparklineSeries.airTemp,
        icon: <ThermometerIcon className="h-6 w-6" />,
      },
      {
        title: 'pH',
        value: formatMetricValue(metrics.ph, 1),
        unit: '',
        norm: '5.8 – 6.5',
        color: '#7DD3FC',
        values: sparklineSeries.ph,
        icon: <PhIcon className="h-6 w-6" />,
      },
      {
        title: 'EC',
        value: formatMetricValue(metrics.ec, 2),
        unit: 'mS/cm',
        norm: '1.2 – 1.6 mS/cm',
        color: '#F7C948',
        values: sparklineSeries.ec,
        icon: <EcIcon className="h-6 w-6" />,
      },
    ],
    [metrics],
  )

  const selectedCrop = useMemo(
    () => crops.find((crop) => crop.slug === selectedCropSlug) || crops[0] || FALLBACK_CROPS[0],
    [crops, selectedCropSlug],
  )

  const manualDevices = useMemo(
    () => [
      {
        key: 'fans',
        title: 'Вентиляция',
        statusText: devices.fans.enabled ? 'Состояние: включено' : 'Состояние: выключено',
        icon: <FanIcon className="h-6 w-6" />,
        accent: '#75F08D',
      },
      {
        key: 'lights',
        title: 'Освещение',
        statusText: devices.lights.enabled ? 'Состояние: включено' : 'Состояние: выключено',
        icon: <LightIcon className="h-6 w-6" />,
        accent: '#FFD667',
      },
      {
        key: 'pumps',
        title: 'Полив',
        statusText: devices.pumps.enabled ? 'Состояние: включено' : 'Состояние: выключено',
        icon: <PumpIcon className="h-6 w-6" />,
        accent: '#8EC8FF',
      },
    ],
    [devices],
  )

  const handleToggle = (key) => async (enabled) => {
    const deviceType = {
      fans: 'fan',
      lights: 'light',
      pumps: 'pump',
    }[key]

    const deviceLabel = {
      fans: 'вентиляторы',
      lights: 'освещение',
      pumps: 'насосы',
    }[key]

    setDevices((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        enabled,
      },
    }))

    try {
      await requestJson('/api/device/control', {
        method: 'POST',
        body: JSON.stringify({
          target_id: 'tray_1',
          device_type: deviceType,
          state: enabled ? 'ON' : 'OFF',
        }),
      })
      pushThought(`${enabled ? 'Включаю' : 'Выключаю'} ${deviceLabel}.`)
    } catch (error) {
      console.error(`Failed to toggle ${deviceType}`, error)
      setDevices((prev) => ({
        ...prev,
        [key]: {
          ...prev[key],
          enabled: !enabled,
        },
      }))
      pushThought(`Не удалось отправить команду на ${deviceLabel}.`)
    }
  }

  const handleStartCycle = async () => {
    if (!selectedCropSlug || currentCycle) return

    setIsCycleLoading(true)
    setCycleError('')
    try {
      const cycle = await requestJson('/api/cycles/start', {
        method: 'POST',
        body: JSON.stringify({
          crop_slug: selectedCropSlug,
          tray_id: DEFAULT_TRAY_ID,
        }),
      })
      setCurrentCycle(cycle)
      pushThought(`Цикл выращивания запущен: ${getCropLabel(selectedCrop)}.`)
    } catch (error) {
      console.error('Failed to start growing cycle', error)
      if (error.status === 409) {
        setCycleError('Цикл уже запущен')
        try {
          await loadCurrentCycle()
        } catch (loadError) {
          console.error('Failed to refresh current cycle after conflict', loadError)
        }
      } else {
        setCycleError(getErrorMessage(error, 'Не удалось запустить цикл. Проверьте backend.'))
      }
    } finally {
      setIsCycleLoading(false)
    }
  }

  const handleFinishCycle = async () => {
    if (!currentCycle) return

    setIsCycleLoading(true)
    setCycleError('')
    try {
      await requestJson('/api/cycles/end', {
        method: 'POST',
        body: JSON.stringify({
          tray_id: DEFAULT_TRAY_ID,
        }),
      })
      setCurrentCycle(null)
      await loadCurrentCycle()
      pushThought('Цикл выращивания завершён.')
    } catch (error) {
      console.error('Failed to finish growing cycle', error)
      setCycleError(getErrorMessage(error, 'Не удалось завершить цикл. Активный цикл не найден.'))
      try {
        await loadCurrentCycle()
      } catch (loadError) {
        console.error('Failed to refresh current cycle after end error', loadError)
      }
    } finally {
      setIsCycleLoading(false)
    }
  }

  const handleSendMessage = async () => {
    const text = chatInput.trim()
    if (!text || isChatThinking) return

    const userMessage = {
      id: makeId(),
      from: 'user',
      text,
      time: formatTime(),
    }

    setMessages((prev) => [...prev, userMessage])
    setChatInput('')
    setIsChatThinking(true)

    try {
      const data = await requestJson('/api/chat', {
        method: 'POST',
        body: JSON.stringify({
          messages: buildChatHistory(messages, userMessage),
        }),
      })

      pushAssistantMessage(data.reply || 'Недостаточно данных для ответа.')
    } catch (error) {
      console.error('Failed to send chat message', error)

      pushThought('Не удалось получить ответ от backend.')
      pushAssistantMessage('Не удалось подключиться к ассистенту. Проверьте backend.')
    } finally {
      setIsChatThinking(false)
    }
  }

  const renderCropCard = (crop) => {
    const visual = getCropVisual(crop.slug)
    const isSelected = selectedCropSlug === crop.slug

    return (
      <button
        key={crop.slug}
        type="button"
        onClick={() => {
          setSelectedCropSlug(crop.slug)
          setCycleError('')
        }}
        className={`relative min-h-[96px] max-w-full overflow-hidden rounded-[20px] border p-3 text-left transition duration-200 sm:min-h-[108px] ${
          isSelected
            ? 'border-emerald-300/80 bg-emerald-400/10 shadow-[0_0_28px_rgba(52,211,153,0.20)]'
            : 'border-white/8 bg-white/[0.045] hover:border-white/18 hover:bg-white/[0.065]'
        }`}
      >
        <div className={`absolute inset-0 bg-gradient-to-br ${visual.gradient}`} />
        <div className="relative flex h-full min-w-0 flex-col items-center justify-center gap-2">
          <div className="text-[34px] leading-none drop-shadow-[0_0_22px_rgba(52,211,153,0.28)] sm:text-[40px]">
            {visual.image ? (
              <img
                src={visual.image}
                alt=""
                aria-hidden="true"
                className="h-12 w-12 object-contain drop-shadow-[0_0_22px_rgba(52,211,153,0.28)] sm:h-14 sm:w-14"
              />
            ) : (
              visual.emoji
            )}
          </div>
          <div className="max-w-full truncate text-center text-[13px] font-semibold leading-tight text-white sm:text-[14px]">
            {getCropLabel(crop)}
          </div>
        </div>
        {isSelected ? (
          <div className="absolute right-3 top-3 flex h-7 w-7 items-center justify-center rounded-full bg-emerald-300 text-slate-950 shadow-[0_0_18px_rgba(52,211,153,0.45)]">
            ✓
          </div>
        ) : null}
      </button>
    )
  }

  const renderCycleControl = () => {
    const activeCropName = currentCycle?.crop_name_ru || getCropLabel(selectedCrop)
    const activeVersion = currentCycle?.version_label || selectedCrop?.version_label || 'v1.0'
    const isActive = Boolean(currentCycle)
    const previewVisual = getCropVisual(currentCycle?.crop_slug || selectedCrop?.slug)

    return (
      <GlassCard className="flex min-h-0 max-w-full flex-col rounded-[28px] min-[1700px]:h-full min-[1700px]:overflow-hidden">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-[22px] font-semibold tracking-tight md:text-[24px]">Управление циклом</div>
            <p className="mt-1.5 max-w-2xl text-sm text-white/62">
              {isActive ? 'Текущий цикл выращивания закреплён за лотком.' : 'Выберите культуру и запустите новый цикл выращивания.'}
            </p>
          </div>
          <div className={`rounded-full border px-4 py-2 text-sm ${isActive ? 'border-emerald-300/30 bg-emerald-400/12 text-emerald-200' : 'border-white/10 bg-white/6 text-white/68'}`}>
            {isActive ? 'Активный цикл' : 'Цикл не запущен'}
          </div>
        </div>

        {cycleError ? (
          <div className="mt-4 rounded-[18px] border border-amber-300/20 bg-amber-300/10 px-4 py-3 text-sm text-amber-100">
            {cycleError}
          </div>
        ) : null}

        <div className={`mt-5 grid max-w-full grid-cols-1 gap-4 min-[1700px]:min-h-0 min-[1700px]:flex-1 ${isActive ? 'min-[1700px]:grid-cols-[minmax(0,0.75fr)_minmax(280px,0.9fr)]' : 'min-[1700px]:grid-cols-[minmax(260px,0.9fr)_minmax(300px,1fr)]'}`}>
          {!isActive ? (
            <div className="min-w-0 max-w-full rounded-[26px] border border-white/8 bg-white/[0.035] p-4">
              <div className="mb-4 text-lg font-semibold text-white">Выбор культуры</div>
              <div className="custom-scrollbar max-h-[260px] overflow-y-auto overflow-x-hidden pr-2 sm:max-h-[300px] min-[1700px]:max-h-[300px]">
                <div className="grid grid-cols-2 gap-3 max-[360px]:grid-cols-1">
                  {crops.map(renderCropCard)}
                </div>
              </div>
            </div>
          ) : (
            <div className="min-w-0 max-w-full rounded-[26px] border border-emerald-300/16 bg-emerald-400/[0.045] p-5">
              <div className="flex h-full min-h-[260px] flex-col justify-between gap-6">
                <div className="min-w-0">
                  <div className="inline-flex items-center gap-2 rounded-full border border-emerald-300/25 bg-emerald-300/10 px-3 py-1 text-sm text-emerald-200">
                    <span className="h-2 w-2 rounded-full bg-emerald-300" />
                    Активный цикл
                  </div>
                  <div className="mt-6 max-w-full truncate text-[30px] font-semibold leading-tight text-white">{activeCropName}</div>
                  <p className="mt-2 text-sm text-white/58">Статус: active / в норме</p>
                </div>
                <button
                  type="button"
                  disabled
                  className="w-full rounded-[18px] border border-white/8 bg-white/[0.04] px-5 py-4 text-sm font-semibold text-white/42"
                >
                  Цикл уже запущен
                </button>
              </div>
            </div>
          )}

          <div className="min-w-0 max-w-full rounded-[26px] border border-white/8 bg-white/[0.035] p-4 sm:p-5">
            <div className="flex min-h-[260px] flex-col min-[1700px]:h-full min-[1700px]:min-h-0">
              <div>
                <div className="text-lg font-semibold text-white">{isActive ? 'Параметры цикла' : 'Предпросмотр цикла'}</div>
                <p className="mt-1 text-sm text-white/58">
                  {isActive ? 'Цикл выполняется по активной агротехкарте.' : 'Проверьте параметры и подтвердите запуск.'}
                </p>
              </div>

              <div className="mt-5 grid min-w-0 flex-1 items-center gap-5 md:grid-cols-[112px_minmax(0,1fr)]">
                <div className={`mx-auto flex aspect-square w-[112px] items-center justify-center rounded-[28px] border border-emerald-300/18 bg-gradient-to-br ${previewVisual.gradient} text-[58px] shadow-[0_0_34px_rgba(52,211,153,0.10)]`}>
                  {previewVisual.image ? (
                    <img
                      src={previewVisual.image}
                      alt={activeCropName}
                      className="h-24 w-24 object-contain drop-shadow-[0_0_28px_rgba(52,211,153,0.22)]"
                    />
                  ) : (
                    previewVisual.emoji
                  )}
                </div>

                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="min-w-0 max-w-full truncate text-[24px] font-semibold leading-tight text-white md:text-[28px]">{activeCropName}</div>
                    {isActive ? (
                      <span className="rounded-full border border-emerald-300/25 bg-emerald-300/10 px-3 py-1 text-sm text-emerald-200">
                        в норме
                      </span>
                    ) : null}
                  </div>

                  <div className="mt-5 divide-y divide-white/8">
                    {[
                      ['Агротехкарта', activeVersion],
                      ['День цикла', currentCycle?.day_number || 1],
                      ['Лоток', currentCycle?.tray_id || DEFAULT_TRAY_ID],
                    ].map(([label, value]) => (
                      <div key={label} className="flex items-center justify-between gap-4 py-3 text-sm">
                        <span className="text-white/54">{label}</span>
                        <span className="font-semibold text-white/88">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-4 grid min-w-0 gap-3 md:grid-cols-[minmax(0,1fr)_140px]">
                {!isActive ? (
                  <>
                    <button
                      type="button"
                      onClick={handleStartCycle}
                      disabled={isCycleLoading}
                      className="inline-flex min-h-[56px] items-center justify-center gap-3 rounded-[20px] border border-violet-200/30 bg-gradient-to-r from-violet-500 to-fuchsia-600 px-5 py-3 font-semibold text-white shadow-[0_0_28px_rgba(168,85,247,0.28)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-55"
                    >
                      <PlayIcon className="h-4 w-4" />
                      {isCycleLoading ? 'Запуск...' : 'Подтвердить запуск'}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setCycleError('')
                        setSelectedCropSlug(crops[0]?.slug || 'basil')
                      }}
                      className="min-h-[56px] rounded-[20px] border border-white/10 bg-white/[0.035] px-5 py-3 font-semibold text-white/72 transition hover:bg-white/[0.065]"
                    >
                      Отмена
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={handleFinishCycle}
                    disabled={isCycleLoading}
                    className="min-h-[56px] rounded-[20px] border border-rose-200/20 bg-rose-500/16 px-5 py-3 font-semibold text-rose-100 transition hover:bg-rose-500/22 disabled:cursor-not-allowed disabled:opacity-55 sm:col-span-2"
                  >
                    {isCycleLoading ? 'Завершение...' : 'Закончить цикл'}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </GlassCard>
    )
  }

  const renderMonitoring = () => (
    <div className="flex min-w-0 max-w-full flex-col gap-3 min-[1700px]:h-full min-[1700px]:min-h-0">
      <section className="min-w-0 max-w-full">
        <div className="custom-scrollbar max-w-full overflow-x-auto overflow-y-hidden">
          <div className="grid min-w-[1120px] grid-cols-5 gap-3 min-[1700px]:min-w-0">
            {metricsList.map((item) => (
              <div key={item.title} className="min-w-0">
                <MetricCard {...item} />
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="grid min-w-0 grid-cols-1 gap-4 min-[1700px]:min-h-0 min-[1700px]:flex-1 min-[1700px]:grid-cols-[minmax(0,1fr)_330px] min-[1900px]:grid-cols-[minmax(0,1fr)_360px]">
        {renderCycleControl()}

        <div className="min-h-[320px] min-w-0 min-[1700px]:min-h-0">
          <ThoughtStream thoughts={thoughts} className="h-full" />
        </div>
      </div>
    </div>
  )

  const renderManual = () => (
    <div className="grid min-w-0 max-w-full gap-4 min-[1700px]:h-full min-[1700px]:min-h-0 min-[1700px]:grid-rows-[auto_minmax(0,1fr)]">
      <GlassCard className="rounded-[28px]">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[22px] font-semibold tracking-tight md:text-[24px]">Устройства</div>
            <p className="mt-1.5 text-sm text-white/62">Быстрый доступ к ключевым системам.</p>
          </div>
          <SlidersIcon className="h-6 w-6 text-white/25" />
        </div>

        <div className="mt-5 grid min-w-0 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {manualDevices.map((device) => (
            <DeviceCard
              key={device.key}
              title={device.title}
              statusText={device.statusText}
              level={devices[device.key].level}
              enabled={devices[device.key].enabled}
              onToggle={handleToggle(device.key)}
              icon={device.icon}
              accent={device.accent}
              showProgress={false}
            />
          ))}
        </div>
      </GlassCard>

      <LedTimeline
        stages={ledStages}
        activeIndex={activeLedStage}
        isPlaying={isLedPlaying}
        onPlay={() => {
          setActiveLedStage(0)
          setIsLedPlaying(true)
        }}
        compact
      />
    </div>
  )

  return (
    <div className="farm-shell relative min-h-screen overflow-x-hidden px-3 py-3 md:px-4 md:py-4 lg:px-6 lg:py-6 min-[1700px]:h-screen min-[1700px]:overflow-hidden">
      <div className="mx-auto flex w-full max-w-[1800px] flex-col gap-4 min-[1700px]:h-full">
        <HeaderBar
          mode={mode}
          setMode={setMode}
          currentTime={currentTime}
          currentDate={currentDate}
        />

        <main className="grid min-w-0 gap-4 min-[1700px]:min-h-0 min-[1700px]:flex-1 min-[1700px]:grid-cols-[minmax(0,1fr)_340px] min-[1900px]:grid-cols-[minmax(0,1fr)_360px]">
          <div className="flex min-w-0 flex-col min-[1700px]:h-full min-[1700px]:min-h-0">{mode === 'monitoring' ? renderMonitoring() : renderManual()}</div>

          <aside className="flex min-h-[520px] min-w-0 flex-col min-[1700px]:h-full min-[1700px]:min-h-0">
            <ChatPanel
              messages={messages}
              input={chatInput}
              onInput={setChatInput}
              onSend={handleSendMessage}
              isThinking={isChatThinking}
              thinkingSteps={CHAT_THINKING_STEPS}
              className="flex-1"
            />
          </aside>
        </main>
      </div>
    </div>
  )
}
