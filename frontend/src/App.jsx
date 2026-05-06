import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
  BrainIcon,
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
const DEV_FEATURES_ENABLED = import.meta.env.VITE_DEV_FEATURES_ENABLED === 'true'
const DEMO_CROP_FALLBACK = [
  { slug: 'mint', name_ru: 'Мята' },
  { slug: 'arugula', name_ru: 'Руккола' },
  { slug: 'basil', name_ru: 'Базилик' },
  { slug: 'cilantro', name_ru: 'Кинза' },
]
const PH_TARGET_INITIAL_FORM = {
  targetPh: '',
  tolerance: '0.1',
  autodosingEnabled: false,
}
const LEARNING_STEPS = [
  { key: 'questionnaire_saved', label: 'Опросник сохранён' },
  { key: 'telemetry_collected', label: 'Телеметрия собрана' },
  { key: 'ph_dosing_collected', label: 'События pH-дозирования учтены' },
  { key: 'alerts_collected', label: 'Алерты EC / pH / температуры учтены' },
  { key: 'ai_analysis', label: 'AI-анализ выполняется' },
  { key: 'proposal_created', label: 'Предложение новой АгроТехКарты' },
  { key: 'new_version_saved', label: 'Новая версия' },
]
const LEARNING_STEP_KEYS = LEARNING_STEPS.map((step) => step.key)
const LEARNING_POLL_INTERVAL_MS = 4000
const LEARNING_VISUAL_STEP_MS = 750

const FINISH_CYCLE_INITIAL_FORM = {
  harvest_status: 'suitable',
  harvest_mass_grams: '',
  completion_reason: 'planned',
  problem_severity: 'unknown',
  problem_phase: 'unknown',
  plant_appearance: {
    healthy: true,
    stretched: false,
    yellow_leaves: false,
    wilted_leaves: false,
    small_leaves: false,
    spots_or_damage: false,
    mold: false,
    poor_roots: false,
  },
  cycle_problems: {
    solution: {
      ph_out_of_range: false,
      ec_out_of_range: false,
      weak_growth: false,
      leaf_edge_burn: false,
    },
    light: {
      stretched_due_to_light: false,
      pale_leaves: false,
      leaning_to_light: false,
      overheating: false,
    },
    irrigation: {
      plants_wilted: false,
      substrate_dried: false,
      excess_moisture: false,
      mold_due_to_humidity: false,
    },
    climate: {
      too_hot: false,
      too_cold: false,
      humidity_too_low: false,
      humidity_too_high: false,
    },
  },
  manual_actions: {
    adjusted_ph: false,
    adjusted_ec: false,
    changed_or_added_solution: false,
    added_water: false,
    moved_lamp: false,
    rearranged_plants: false,
    cleaned_tank: false,
    other: false,
  },
  followed_ai_advice: 'unknown',
  ai_advice_helpfulness: 'unknown',
  operator_comment: '',
}

const HARVEST_STATUS_OPTIONS = [
  { value: 'suitable', label: 'Урожай получен и пригоден' },
  { value: 'partial', label: 'Получен частично' },
  { value: 'weak_suitable', label: 'Слабый, но пригоден' },
  { value: 'failed', label: 'Непригоден / цикл неудачный' },
  { value: 'stopped_early', label: 'Цикл остановлен досрочно' },
]

const COMPLETION_REASON_OPTIONS = [
  { value: 'planned', label: 'Плановое завершение' },
  { value: 'harvest_ready', label: 'Урожай готов' },
  { value: 'plant_problems', label: 'Проблемы с растениями' },
  { value: 'test_cycle', label: 'Тестовый цикл' },
  { value: 'other', label: 'Другое' },
]

const PROBLEM_SEVERITY_OPTIONS = [
  { value: 'none', label: 'Проблем почти не было' },
  { value: 'minor', label: 'Небольшие проблемы' },
  { value: 'noticeable', label: 'Заметные проблемы' },
  { value: 'bad', label: 'Цикл прошёл плохо' },
  { value: 'unknown', label: 'Сложно сказать' },
]

const PROBLEM_PHASE_OPTIONS = [
  { value: 'early', label: 'В начале цикла' },
  { value: 'middle', label: 'В середине цикла' },
  { value: 'end', label: 'В конце цикла' },
  { value: 'whole_cycle', label: 'На протяжении всего цикла' },
  { value: 'unknown', label: 'Сложно сказать' },
]

const AI_ADVICE_FOLLOW_OPTIONS = [
  { value: 'yes', label: 'Да' },
  { value: 'partial', label: 'Частично' },
  { value: 'no', label: 'Нет' },
  { value: 'no_advice', label: 'Советов не было' },
  { value: 'unknown', label: 'Сложно сказать' },
]

const AI_ADVICE_HELPFULNESS_OPTIONS = [
  { value: 'yes', label: 'Да' },
  { value: 'partial', label: 'Частично' },
  { value: 'no', label: 'Нет' },
  { value: 'worse', label: 'Стало хуже' },
  { value: 'unknown', label: 'Сложно сказать' },
]

const PLANT_APPEARANCE_FIELDS = [
  { key: 'healthy', label: 'Растения выглядели здоровыми' },
  { key: 'stretched', label: 'Растения вытянулись' },
  { key: 'yellow_leaves', label: 'Листья пожелтели' },
  { key: 'wilted_leaves', label: 'Листья были вялыми' },
  { key: 'small_leaves', label: 'Листья были мелкими' },
  { key: 'spots_or_damage', label: 'Были пятна / повреждения' },
  { key: 'mold', label: 'Была плесень' },
  { key: 'poor_roots', label: 'Корни выглядели плохо' },
]

const CYCLE_PROBLEM_GROUPS = [
  {
    key: 'solution',
    title: 'Раствор',
    fields: [
      { key: 'ph_out_of_range', label: 'pH выходил из нормы' },
      { key: 'ec_out_of_range', label: 'EC выходил из нормы' },
      { key: 'weak_growth', label: 'Слабый рост' },
      { key: 'leaf_edge_burn', label: 'Ожоги краёв листьев' },
    ],
  },
  {
    key: 'light',
    title: 'Свет',
    fields: [
      { key: 'stretched_due_to_light', label: 'Растения вытягивались' },
      { key: 'pale_leaves', label: 'Листья были бледными' },
      { key: 'leaning_to_light', label: 'Растения тянулись к свету' },
      { key: 'overheating', label: 'Был перегрев' },
    ],
  },
  {
    key: 'irrigation',
    title: 'Полив / влажность',
    fields: [
      { key: 'plants_wilted', label: 'Растения вяли' },
      { key: 'substrate_dried', label: 'Субстрат пересыхал' },
      { key: 'excess_moisture', label: 'Был переизбыток влаги' },
      { key: 'mold_due_to_humidity', label: 'Была плесень' },
    ],
  },
  {
    key: 'climate',
    title: 'Климат',
    fields: [
      { key: 'too_hot', label: 'Было слишком жарко' },
      { key: 'too_cold', label: 'Было слишком холодно' },
      { key: 'humidity_too_low', label: 'Влажность была слишком низкой' },
      { key: 'humidity_too_high', label: 'Влажность была слишком высокой' },
    ],
  },
]

const MANUAL_ACTION_FIELDS = [
  { key: 'adjusted_ph', label: 'Корректировал pH' },
  { key: 'adjusted_ec', label: 'Корректировал EC' },
  { key: 'changed_or_added_solution', label: 'Менял / доливал раствор' },
  { key: 'added_water', label: 'Доливал воду' },
  { key: 'moved_lamp', label: 'Менял положение лампы' },
  { key: 'rearranged_plants', label: 'Переставлял растения' },
  { key: 'cleaned_tank', label: 'Чистил ёмкость' },
  { key: 'other', label: 'Другое' },
]

function createInitialFinishCycleForm() {
  return {
    ...FINISH_CYCLE_INITIAL_FORM,
    plant_appearance: { ...FINISH_CYCLE_INITIAL_FORM.plant_appearance },
    cycle_problems: {
      solution: { ...FINISH_CYCLE_INITIAL_FORM.cycle_problems.solution },
      light: { ...FINISH_CYCLE_INITIAL_FORM.cycle_problems.light },
      irrigation: { ...FINISH_CYCLE_INITIAL_FORM.cycle_problems.irrigation },
      climate: { ...FINISH_CYCLE_INITIAL_FORM.cycle_problems.climate },
    },
    manual_actions: { ...FINISH_CYCLE_INITIAL_FORM.manual_actions },
  }
}

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

function formatPhRangeValue(value) {
  return Number.isFinite(value) ? value.toFixed(1) : null
}

function getCurrentCycleNorms(currentCycle) {
  if (!currentCycle || typeof currentCycle !== 'object') return null

  const candidates = [
    currentCycle.norms,
    currentCycle.agrotech_card?.norms,
    currentCycle.agrotechCard?.norms,
    currentCycle.revision?.norms,
    currentCycle.active_revision?.norms,
    currentCycle.activeRevision?.norms,
    currentCycle.card_revision?.norms,
    currentCycle.cardRevision?.norms,
  ]

  return candidates.find((value) => value && typeof value === 'object' && !Array.isArray(value)) || null
}

function parseNormRange(value) {
  if (Array.isArray(value) && value.length >= 2) {
    const min = toNumberOrNull(value[0])
    const max = toNumberOrNull(value[1])
    return min !== null && max !== null ? { min, max } : null
  }

  if (!value || typeof value !== 'object') return null

  const rangeKeys = [
    ['min', 'max'],
    ['low', 'high'],
    ['from', 'to'],
    ['target_min', 'target_max'],
    ['optimal_min', 'optimal_max'],
    ['lower', 'upper'],
  ]

  for (const [minKey, maxKey] of rangeKeys) {
    const min = toNumberOrNull(value[minKey])
    const max = toNumberOrNull(value[maxKey])
    if (min !== null && max !== null) {
      return { min, max }
    }
  }

  return null
}

function findNormRange(norms, aliases) {
  if (!norms || typeof norms !== 'object') return null

  const entriesByLowerKey = Object.fromEntries(
    Object.entries(norms).map(([key, value]) => [key.toLowerCase(), value]),
  )

  for (const alias of aliases) {
    const directValue = norms[alias]
    const lowerValue = entriesByLowerKey[alias.toLowerCase()]
    const range = parseNormRange(directValue ?? lowerValue)
    if (range) return range
  }

  return null
}

function formatNumberForNorm(value) {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)))
}

function formatMetricNorm(currentCycle, norms, aliases, unit) {
  if (!currentCycle) return 'цикл не запущен'

  const range = findNormRange(norms, aliases)
  if (!range) return 'норма не задана'

  return `${formatNumberForNorm(range.min)} – ${formatNumberForNorm(range.max)}${unit ? ` ${unit}` : ''}`
}

function buildMetricNormLabels(currentCycle) {
  const norms = getCurrentCycleNorms(currentCycle)

  return {
    waterTemp: formatMetricNorm(
      currentCycle,
      norms,
      ['water_temp', 'waterTemp', 'solution_temperature', 'solutionTemperature'],
      '°C',
    ),
    airHumidity: formatMetricNorm(
      currentCycle,
      norms,
      ['humidity', 'air_humidity', 'airHumidity'],
      '%',
    ),
    airTemp: formatMetricNorm(
      currentCycle,
      norms,
      ['air_temp', 'airTemp', 'temperature'],
      '°C',
    ),
    ph: formatMetricNorm(currentCycle, norms, ['ph', 'pH'], ''),
    ec: formatMetricNorm(currentCycle, norms, ['ec', 'EC'], 'mS/cm'),
  }
}

function getLearningStepIndex(stepKey) {
  return LEARNING_STEP_KEYS.indexOf(stepKey)
}

function getVisualLearningStepIndex(status) {
  if (!status) return -1
  if (status.status === 'completed') return LEARNING_STEP_KEYS.length
  const currentIndex = getLearningStepIndex(status.current_step)
  if (currentIndex >= 0) return currentIndex
  const completedSteps = Array.isArray(status.completed_steps) ? status.completed_steps : []
  return completedSteps.reduce((maxIndex, stepKey) => {
    const stepIndex = getLearningStepIndex(stepKey)
    return stepIndex > maxIndex ? stepIndex : maxIndex
  }, -1)
}

function getLearningTargetStepIndex(status) {
  if (!status) return -1
  if (status.status === 'completed') return LEARNING_STEP_KEYS.length
  const currentIndex = getLearningStepIndex(status.current_step)
  if (currentIndex >= 0) return currentIndex
  const completedSteps = Array.isArray(status.completed_steps) ? status.completed_steps : []
  const maxCompletedIndex = completedSteps.reduce((maxIndex, stepKey) => {
    const stepIndex = getLearningStepIndex(stepKey)
    return stepIndex > maxIndex ? stepIndex : maxIndex
  }, -1)
  return Math.min(maxCompletedIndex + 1, LEARNING_STEP_KEYS.length - 1)
}

function buildVisualLearningStatus(baseStatus, currentIndex, statusOverride = 'running') {
  if (!baseStatus) return null
  const normalizedIndex = Math.max(0, Math.min(currentIndex, LEARNING_STEP_KEYS.length - 1))
  return {
    ...baseStatus,
    status: statusOverride,
    current_step: LEARNING_STEP_KEYS[normalizedIndex],
    completed_steps: LEARNING_STEP_KEYS.slice(0, normalizedIndex),
  }
}

function buildFinalVisualLearningStatus(baseStatus) {
  if (!baseStatus) return null
  return {
    ...baseStatus,
    status: baseStatus.status,
    current_step: baseStatus.status === 'completed' ? null : baseStatus.current_step,
    completed_steps: baseStatus.status === 'completed' ? [...LEARNING_STEP_KEYS] : baseStatus.completed_steps || [],
  }
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

function getCropLabel(crop) {
  if (!crop) return 'Культура'
  return crop.name_ru || crop.crop_name_ru || CROP_VISUALS[crop.slug]?.label || crop.slug
}

function formatTrayName(trayId) {
  if (!trayId || trayId === DEFAULT_TRAY_ID) return 'Основной модуль'
  return `Модуль ${String(trayId).replace(/^tray_/, '')}`
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

function hasSelectedRequiredFinishCycleFields(form) {
  return Boolean(
    form.harvest_status &&
    form.completion_reason &&
    form.problem_severity &&
    form.problem_phase &&
    form.followed_ai_advice &&
    form.ai_advice_helpfulness,
  )
}

function hasAnyTruthyNestedValue(value) {
  if (!value || typeof value !== 'object') return false

  return Object.values(value).some((entry) => {
    if (entry && typeof entry === 'object') {
      return hasAnyTruthyNestedValue(entry)
    }

    return Boolean(entry)
  })
}

function hasProblemContradiction(form) {
  if (form.problem_severity !== 'none') return false

  const hasNegativePlantAppearance = Object.entries(form.plant_appearance || {}).some(
    ([key, value]) => key !== 'healthy' && Boolean(value),
  )

  return (
    hasNegativePlantAppearance ||
    hasAnyTruthyNestedValue(form.cycle_problems) ||
    hasAnyTruthyNestedValue(form.manual_actions)
  )
}

function FinishCycleModal({
  currentCycle,
  form,
  setForm,
  error,
  isLoading,
  onClose,
  onSubmit,
}) {
  const isFormValid = hasSelectedRequiredFinishCycleFields(form)
  const showProblemContradictionWarning = hasProblemContradiction(form)

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && !isLoading) {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isLoading, onClose])

  const updateField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const updatePlantAppearance = (field, checked) => {
    setForm((prev) => ({
      ...prev,
      plant_appearance: {
        ...prev.plant_appearance,
        [field]: checked,
      },
    }))
  }

  const updateCycleProblem = (group, field, checked) => {
    setForm((prev) => ({
      ...prev,
      cycle_problems: {
        ...prev.cycle_problems,
        [group]: {
          ...prev.cycle_problems[group],
          [field]: checked,
        },
      },
    }))
  }

  const updateManualAction = (field, checked) => {
    setForm((prev) => ({
      ...prev,
      manual_actions: {
        ...prev.manual_actions,
        [field]: checked,
      },
    }))
  }

  const renderPills = (name, options, value, onChange) => (
    <div className="flex flex-wrap gap-2">
      {options.map((option) => {
        const isSelected = value === option.value
        return (
          <button
            key={`${name}-${option.value}`}
            type="button"
            onClick={() => onChange(option.value)}
            className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
              isSelected
                ? 'border-violet-200/70 bg-gradient-to-r from-violet-500 to-fuchsia-600 text-white shadow-[0_0_22px_rgba(168,85,247,0.28)]'
                : 'border-white/10 bg-white/[0.045] text-white/70 hover:border-white/20 hover:bg-white/[0.07]'
            }`}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )

  const renderCheckbox = (checked, onChange, label) => (
    <label className="flex min-h-[44px] cursor-pointer items-center gap-3 rounded-[16px] border border-white/8 bg-white/[0.035] px-3 py-2 text-sm text-white/78 transition hover:bg-white/[0.06]">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 rounded border-white/20 bg-slate-950 text-violet-400 accent-violet-500"
      />
      <span>{label}</span>
    </label>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/62 px-3 py-4 backdrop-blur-md">
      <div className="absolute inset-0" onClick={isLoading ? undefined : onClose} />
      <form
        onSubmit={onSubmit}
        className="custom-scrollbar relative z-10 flex max-h-[92vh] w-full max-w-4xl flex-col overflow-y-auto rounded-[32px] border border-white/10 bg-slate-950/90 p-5 shadow-[0_24px_80px_rgba(0,0,0,0.45)] sm:p-6"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-[26px] font-semibold tracking-tight text-white">Завершение цикла</h2>
            <p className="mt-1.5 text-sm text-white/62">
              Заполните итоговый опросник перед завершением выращивания.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.045] text-xl text-white/70 transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Закрыть"
          >
            ×
          </button>
        </div>

        <div className="mt-5 grid gap-3 rounded-[24px] border border-emerald-300/14 bg-emerald-400/[0.045] p-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ['Культура', currentCycle?.crop_name_ru || 'Культура'],
            ['АгроТехКарта', currentCycle?.version_label || 'v1.0'],
            ['День цикла', currentCycle?.day_number || 1],
            ['Лоток', formatTrayName(currentCycle?.tray_id || DEFAULT_TRAY_ID)],
          ].map(([label, value]) => (
            <div key={label} className="min-w-0">
              <div className="text-xs uppercase tracking-[0.12em] text-white/38">{label}</div>
              <div className="mt-1 truncate text-sm font-semibold text-white/88">{value}</div>
            </div>
          ))}
        </div>

        {error ? (
          <div className="mt-4 rounded-[18px] border border-amber-300/20 bg-amber-300/10 px-4 py-3 text-sm text-amber-100">
            {error}
          </div>
        ) : null}

        {showProblemContradictionWarning ? (
          <div className="mt-4 rounded-[18px] border border-sky-300/20 bg-sky-300/10 px-4 py-3 text-sm leading-relaxed text-sky-100">
            Вы выбрали, что проблем почти не было, но отметили отдельные признаки проблем. Это нормально, но Нейрогном будет учитывать это как небольшие противоречия при будущем анализе цикла.
          </div>
        ) : null}

        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <section className="rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
            <div className="text-base font-semibold text-white">Итог урожая</div>
            <div className="mt-3">
              {renderPills('harvest_status', HARVEST_STATUS_OPTIONS, form.harvest_status, (value) => updateField('harvest_status', value))}
            </div>
          </section>

          <section className="rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
            <label className="text-base font-semibold text-white" htmlFor="harvest-mass">
              Масса урожая, г <span className="text-white/42">(необязательно)</span>
            </label>
            <input
              id="harvest-mass"
              type="number"
              min="0"
              step="0.1"
              value={form.harvest_mass_grams}
              onChange={(event) => updateField('harvest_mass_grams', event.target.value)}
              className="mt-3 h-12 w-full rounded-[16px] border border-white/10 bg-slate-950/70 px-4 text-white outline-none transition placeholder:text-white/30 focus:border-violet-300/70"
              placeholder="Например: 420"
            />
          </section>
        </div>

        <div className="mt-5 grid gap-5 lg:grid-cols-3">
          <section className="rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
            <div className="text-base font-semibold text-white">Причина завершения</div>
            <div className="mt-3">
              {renderPills('completion_reason', COMPLETION_REASON_OPTIONS, form.completion_reason, (value) => updateField('completion_reason', value))}
            </div>
          </section>

          <section className="rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
            <div className="text-base font-semibold text-white">Общая серьёзность проблем</div>
            <div className="mt-3">
              {renderPills('problem_severity', PROBLEM_SEVERITY_OPTIONS, form.problem_severity, (value) => updateField('problem_severity', value))}
            </div>
          </section>

          <section className="rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
            <div className="text-base font-semibold text-white">Когда проблемы были заметнее</div>
            <div className="mt-3">
              {renderPills('problem_phase', PROBLEM_PHASE_OPTIONS, form.problem_phase, (value) => updateField('problem_phase', value))}
            </div>
          </section>
        </div>

        <section className="mt-5 rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
          <div className="text-base font-semibold text-white">Внешний вид растений</div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {PLANT_APPEARANCE_FIELDS.map((field) => (
              <div key={field.key}>
                {renderCheckbox(
                  Boolean(form.plant_appearance[field.key]),
                  (checked) => updatePlantAppearance(field.key, checked),
                  field.label,
                )}
              </div>
            ))}
          </div>
        </section>

        <section className="mt-5 rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
          <div className="text-base font-semibold text-white">Проблемы во время цикла</div>
          <div className="mt-3 grid gap-3 lg:grid-cols-4">
            {CYCLE_PROBLEM_GROUPS.map((group) => (
              <div key={group.key} className="rounded-[20px] border border-white/8 bg-slate-950/40 p-3">
                <div className="mb-2 text-sm font-semibold text-white/86">{group.title}</div>
                <div className="grid gap-2">
                  {group.fields.map((field) => (
                    <div key={field.key}>
                      {renderCheckbox(
                        Boolean(form.cycle_problems[group.key]?.[field.key]),
                        (checked) => updateCycleProblem(group.key, field.key, checked),
                        field.label,
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-5 rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
          <div className="text-base font-semibold text-white">Ручные действия оператора</div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {MANUAL_ACTION_FIELDS.map((field) => (
              <div key={field.key}>
                {renderCheckbox(
                  Boolean(form.manual_actions[field.key]),
                  (checked) => updateManualAction(field.key, checked),
                  field.label,
                )}
              </div>
            ))}
          </div>
        </section>

        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <section className="rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
            <div className="text-base font-semibold text-white">Следовали ли советам Нейрогнома?</div>
            <div className="mt-3">
              {renderPills('followed_ai_advice', AI_ADVICE_FOLLOW_OPTIONS, form.followed_ai_advice, (value) => updateField('followed_ai_advice', value))}
            </div>
          </section>

          <section className="rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
            <div className="text-base font-semibold text-white">Помогли ли советы?</div>
            <div className="mt-3">
              {renderPills('ai_advice_helpfulness', AI_ADVICE_HELPFULNESS_OPTIONS, form.ai_advice_helpfulness, (value) => updateField('ai_advice_helpfulness', value))}
            </div>
          </section>
        </div>

        <section className="mt-5 rounded-[24px] border border-white/8 bg-white/[0.03] p-4">
          <label className="text-base font-semibold text-white" htmlFor="operator-comment">
            Комментарий
          </label>
          <textarea
            id="operator-comment"
            value={form.operator_comment}
            onChange={(event) => updateField('operator_comment', event.target.value)}
            className="mt-3 min-h-[112px] w-full resize-none rounded-[18px] border border-white/10 bg-slate-950/70 px-4 py-3 text-white outline-none transition placeholder:text-white/30 focus:border-violet-300/70"
            placeholder="Например: растения слегка вытянулись ближе к концу цикла, но в целом урожай пригоден."
          />
        </section>

        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="min-h-[52px] rounded-[18px] border border-white/10 bg-white/[0.045] px-5 py-3 font-semibold text-white/74 transition hover:bg-white/[0.075] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Отмена
          </button>
          <button
            type="submit"
            disabled={isLoading || !isFormValid}
            className={`min-h-[52px] rounded-[18px] border px-5 py-3 font-semibold text-white transition disabled:cursor-not-allowed ${
              isFormValid
                ? 'border-violet-200/30 bg-gradient-to-r from-violet-500 to-fuchsia-600 shadow-[0_0_28px_rgba(168,85,247,0.28)] hover:brightness-110 disabled:opacity-55'
                : 'border-white/8 bg-white/[0.045] text-white/38 opacity-70'
            }`}
          >
            {isLoading ? 'Завершение...' : 'Подтвердить завершение'}
          </button>
        </div>
      </form>
    </div>
  )
}

function LearningStepMarker({ status, index }) {
  if (status === 'error') {
    return (
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-rose-300/55 bg-rose-400/18 text-[11px] font-bold text-rose-100 shadow-[0_0_14px_rgba(251,113,133,0.24)]">
        !
      </span>
    )
  }

  if (status === 'done') {
    return (
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-emerald-300/45 bg-emerald-300/18 text-[11px] font-bold text-emerald-200 shadow-[0_0_14px_rgba(52,211,153,0.18)]">
        ✓
      </span>
    )
  }

  if (status === 'running') {
    return (
      <span className="relative flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-indigo-200/70 bg-indigo-500/25 text-[11px] font-bold text-indigo-100 shadow-[0_0_18px_rgba(99,102,241,0.55)]">
        <span className="absolute inset-[-4px] rounded-full border border-violet-300/25" />
        {index + 1}
      </span>
    )
  }

  return (
    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-white/18 bg-white/[0.025] text-[11px] font-semibold text-white/38">
      {index + 1}
    </span>
  )
}

function LearningWidget({
  isOpen,
  learningStatus,
  learningResult,
  learningResultError,
  loadError,
  onToggle,
  onClose,
  onExpand,
}) {
  const effectiveStatus = learningResult?.status || learningStatus?.status
  const effectiveOutcome = learningResult?.outcome || learningStatus?.outcome
  const status = loadError && !learningResult ? 'failed' : effectiveStatus || 'idle'
  const outcome = effectiveOutcome || null
  const completedSteps = new Set(learningStatus?.completed_steps || [])
  const currentStep = learningStatus?.current_step
  const fallbackSteps = LEARNING_STEPS.map((step) => {
    const label = step.key === 'new_version_saved' && status === 'completed'
      ? outcome === 'no_new_revision'
        ? 'Новая версия не требуется'
        : 'Новая версия сохранена'
      : step.label
    return {
      ...step,
      label,
      status: status === 'completed' || completedSteps.has(step.key)
        ? 'done'
        : status === 'failed' && currentStep === step.key
          ? 'error'
          : currentStep === step.key
            ? 'running'
            : 'pending',
    }
  })
  const learningResultSteps = Array.isArray(learningResult?.steps) && learningResult.steps.length > 0
    ? learningResult.steps
    : null
  let firstResultRunningStepUsed = false
  const steps = learningResultSteps
    ? learningResultSteps.map((step, index) => {
      const isDone = Boolean(step?.done)
      const isRunning = !isDone && status === 'running' && !firstResultRunningStepUsed
      if (isRunning) {
        firstResultRunningStepUsed = true
      }
      return {
        key: step?.key || `learning-result-step-${index}`,
        label: step?.label || '',
        status: isDone ? 'done' : isRunning ? 'running' : 'pending',
      }
    })
    : fallbackSteps
  const canExpand = learningResult
    ? Boolean(learningResult.has_changes && learningResult.can_open_details)
    : effectiveStatus === 'completed' && effectiveOutcome !== 'no_new_revision'
  const isHighlighted = ['running', 'completed'].includes(status)
  const badge = status === 'completed'
    ? outcome === 'no_new_revision'
      ? 'Анализ завершён'
      : 'Обучение завершено'
    : status === 'failed'
      ? 'Ошибка анализа'
      : status === 'running'
        ? 'Выполняется'
        : 'Этапы анализа'
  const badgeClassName = status === 'completed'
    ? 'border-emerald-300/20 bg-emerald-300/10 text-emerald-200'
    : status === 'failed'
      ? 'border-rose-300/24 bg-rose-400/10 text-rose-100'
      : status === 'running'
        ? 'border-indigo-300/24 bg-indigo-400/10 text-indigo-100'
        : 'border-white/10 bg-white/[0.055] text-white/56'
  const orbClassName = status === 'completed'
    ? 'border-emerald-200/45 bg-emerald-400/20 text-emerald-100 shadow-[0_0_24px_rgba(52,211,153,0.34)] hover:bg-emerald-400/28'
    : status === 'failed'
      ? 'border-rose-200/40 bg-rose-400/16 text-rose-100 shadow-[0_0_20px_rgba(251,113,133,0.24)] hover:bg-rose-400/22'
      : isHighlighted
        ? 'border-indigo-200/55 bg-indigo-500/25 text-indigo-100 shadow-[0_0_24px_rgba(99,102,241,0.45)] hover:bg-indigo-500/32'
        : 'border-white/10 bg-white/[0.045] text-white/48 shadow-[0_0_18px_rgba(148,163,184,0.08)] hover:border-white/18 hover:text-white/70'
  const fallbackFooterText = loadError
    ? 'Не удалось загрузить статус обучения'
    : status === 'completed'
      ? outcome === 'no_new_revision'
        ? 'Анализ завершён. АгроТехКарта не изменена.'
        : `Новая версия готова: ${learningStatus?.new_version_label || 'ожидает подтверждения'}`
      : status === 'failed'
        ? learningStatus?.error || 'Анализ остановился с ошибкой. Можно выбрать другую культуру или повторить позже.'
        : status === 'running'
          ? 'Новый цикл этой культуры будет доступен после завершения анализа.'
          : 'Обучение станет доступно после завершения цикла.'

  return (
    <>
      <button
        type="button"
        onClick={onToggle}
        aria-label="Открыть обучение АгроТехКарты"
        className={`relative flex h-11 w-11 shrink-0 items-center justify-center rounded-full border transition ${orbClassName}`}
      >
        {isHighlighted ? <span className="absolute inset-[-5px] rounded-full border border-violet-300/18" /> : null}
        <BrainIcon className="relative h-5 w-5" />
      </button>

      {isOpen ? (
        <div className="absolute left-2 right-2 top-[64px] z-30 max-w-[calc(100vw-32px)] rounded-[24px] border border-white/10 bg-slate-950/80 p-4 shadow-[0_18px_50px_rgba(0,0,0,0.38),0_0_32px_rgba(99,102,241,0.16)] backdrop-blur-xl sm:left-auto sm:right-4 sm:top-[56px] sm:w-[340px]">
          <div className="flex min-w-0 items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-[15px] font-semibold text-white">Обучение АгроТехКарты</div>
              <div className={`mt-2 inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${badgeClassName}`}>
                {badge}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <button
                type="button"
                disabled={!canExpand}
                aria-disabled={!canExpand}
                onClick={() => {
                  if (!canExpand) return
                  onExpand()
                }}
                aria-label="Развернуть обучение АгроТехКарты"
                className={`flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-sm font-semibold text-white/58 transition ${
                  canExpand
                    ? 'hover:bg-white/[0.08] hover:text-white'
                    : 'opacity-40 cursor-not-allowed pointer-events-auto'
                }`}
              >
                ↗
              </button>
              <button
                type="button"
                onClick={onClose}
                aria-label="Свернуть обучение АгроТехКарты"
                className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-sm font-semibold text-white/58 transition hover:bg-white/[0.08] hover:text-white"
              >
                ×
              </button>
            </div>
          </div>

          <div className="mt-4 space-y-2.5">
            {steps.map((step, index) => (
              <div key={step.key} className="flex min-w-0 items-center gap-2.5">
                <LearningStepMarker status={step.status} index={index} />
                <span className={`min-w-0 flex-1 text-[12px] leading-snug ${step.status === 'pending' ? 'text-white/46' : step.status === 'error' ? 'text-rose-100' : 'text-white/82'}`}>
                  {step.label}
                </span>
              </div>
            ))}
          </div>

          <div className="mt-4 rounded-[16px] border border-white/8 bg-white/[0.035] px-3 py-2.5 text-[11px] leading-snug text-white/52">
            {learningResult?.message || fallbackFooterText}
          </div>
        </div>
      ) : null}
    </>
  )
}

function formatLearningNumber(value) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return '—'
  const rounded = parsed.toFixed(1)
  return rounded.endsWith('.0') ? rounded.slice(0, -2) : rounded
}

function getLearningMetricValue(metric, key) {
  return formatLearningNumber(metric?.[key])
}

function getVersionText(versionFrom, versionTo) {
  return versionFrom && versionTo ? `${versionFrom} → ${versionTo}` : 'Версия обновлена'
}

function getLearningText(value, fallback = '—') {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function LearningEvidenceCard({ title, metric, accent = 'cyan', icon }) {
  const accentClassName = {
    cyan: 'border-cyan-300/18 bg-cyan-400/10 text-cyan-200',
    amber: 'border-amber-300/18 bg-amber-300/10 text-amber-200',
    violet: 'border-violet-300/18 bg-violet-400/10 text-violet-200',
    emerald: 'border-emerald-300/18 bg-emerald-400/10 text-emerald-200',
  }[accent] || 'border-cyan-300/18 bg-cyan-400/10 text-cyan-200'

  return (
    <div className="min-w-0 rounded-[18px] border border-white/10 bg-white/[0.035] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.035)]">
      <div className="flex min-w-0 items-center gap-2.5">
        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] border text-[13px] font-bold ${accentClassName}`}>
          {icon}
        </span>
        <div className="min-w-0 truncate text-[14px] font-semibold text-white/88">{title}</div>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2">
        {[
          ['мин', getLearningMetricValue(metric, 'min')],
          ['средн.', getLearningMetricValue(metric, 'avg')],
          ['макс.', getLearningMetricValue(metric, 'max')],
        ].map(([label, value]) => (
          <div key={label} className="min-w-0">
            <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-white/38">{label}</div>
            <div className="mt-1 truncate text-[20px] font-semibold text-white">{value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function LearningEvidenceCounter({ title, value, suffix, accent = 'cyan', icon }) {
  const accentClassName = {
    cyan: 'border-cyan-300/18 bg-cyan-400/10 text-cyan-200',
    amber: 'border-amber-300/18 bg-amber-300/10 text-amber-200',
    violet: 'border-violet-300/18 bg-violet-400/10 text-violet-200',
    emerald: 'border-emerald-300/18 bg-emerald-400/10 text-emerald-200',
  }[accent] || 'border-cyan-300/18 bg-cyan-400/10 text-cyan-200'
  const safeValue = value === null || value === undefined || value === '' ? '0' : String(value)

  return (
    <div className="flex min-w-0 items-center gap-2 rounded-[14px] border border-white/8 bg-white/[0.03] px-2.5 py-2.5">
      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] border text-[15px] font-bold ${accentClassName}`}>
        {icon}
      </span>
      <div className="min-w-0 text-[12px] leading-snug">
        <div className="truncate font-semibold text-white/78">{title}</div>
        <div className="truncate text-white/58">
          <span className="font-semibold text-white">{safeValue}</span> {suffix}
        </div>
      </div>
    </div>
  )
}

function LearningChangesTable({ changes }) {
  const rows = Array.isArray(changes) ? changes : []
  if (rows.length === 0) {
    return (
      <div className="rounded-[16px] border border-white/8 bg-white/[0.025] px-4 py-5 text-sm text-white/58">
        Содержательных изменений АгроТехКарты не найдено.
      </div>
    )
  }

  return (
    <div className="custom-scrollbar overflow-x-auto rounded-[16px] border border-white/8">
      <table className="min-w-[760px] w-full border-collapse text-left text-[13px]">
        <thead className="bg-white/[0.045] text-white/62">
          <tr>
            {['Параметр', 'Было', 'Стало', 'Причина'].map((title) => (
              <th key={title} className="border-b border-white/8 px-3 py-3 font-semibold">{title}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/8">
          {rows.map((change, index) => (
            <tr key={`${change?.parameter || 'change'}-${index}`} className="bg-white/[0.018]">
              <td className="px-3 py-3 font-semibold text-white/84">{getLearningText(change?.parameter)}</td>
              <td className="px-3 py-3 text-white/64">{getLearningText(change?.before)}</td>
              <td className="bg-emerald-400/[0.09] px-3 py-3 font-semibold text-emerald-300">{getLearningText(change?.after)}</td>
              <td className="px-3 py-3 text-white/66">{getLearningText(change?.reason, 'Параметр скорректирован по результатам анализа завершённого цикла.')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function LearningResultModal({ learningResult, onClose }) {
  const canRender = Boolean(learningResult?.can_open_details && learningResult?.has_changes)
  if (!canRender) return null

  const evidence = learningResult?.evidence || {}
  const steps = Array.isArray(learningResult?.steps) ? learningResult.steps : []
  const versionText = getVersionText(learningResult?.version_from, learningResult?.version_to)
  const nextVersionText = learningResult?.version_to
    ? `Следующий цикл этой культуры будет запущен уже по версии ${learningResult.version_to}.`
    : 'Следующий цикл этой культуры будет запущен с актуальной версией АгроТехКарты.'
  const subtitle = getLearningText(
    learningResult?.message,
    'Анализ завершён. Сформирована новая версия АгроТехКарты.',
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-3 py-4 backdrop-blur-lg">
      <div className="custom-scrollbar relative flex max-h-[94vh] w-full max-w-[1400px] flex-col overflow-y-auto rounded-[28px] border border-white/12 bg-slate-950/90 p-4 shadow-[0_26px_90px_rgba(0,0,0,0.58),0_0_54px_rgba(99,102,241,0.18)] sm:p-6">
        <div className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-white/26 to-transparent" />
        <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <h2 className="text-[26px] font-semibold tracking-tight text-white md:text-[32px]">Результат обучения цикла</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-white/62 md:text-base">{subtitle}</p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2 lg:justify-end">
            <span className="inline-flex h-10 items-center gap-2 rounded-full border border-emerald-300/28 bg-emerald-400/10 px-3 text-sm font-semibold text-emerald-200">
              <span className="text-lg leading-none">✓</span>
              Обучение завершено
            </span>
            <span className="inline-flex h-10 items-center gap-2 rounded-full border border-emerald-300/16 bg-white/[0.04] px-3 text-sm font-semibold text-white/86">
              <span className="flex h-7 w-7 items-center justify-center rounded-full border border-emerald-300/18 bg-emerald-400/10 text-emerald-300">⌁</span>
              {getLearningText(learningResult?.crop_name_ru, 'Культура')}
            </span>
            <span className="inline-flex h-10 items-center rounded-full border border-white/10 bg-white/[0.04] px-3 text-sm font-semibold text-white/78">
              {versionText}
            </span>
            <button
              type="button"
              className="hidden h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/[0.045] text-xl text-white/64 transition hover:bg-white/[0.08] hover:text-white sm:flex"
              aria-label="Меню результата обучения"
            >
              ≡
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/[0.045] text-2xl leading-none text-white/72 transition hover:bg-white/[0.08] hover:text-white"
              aria-label="Закрыть"
            >
              ×
            </button>
          </div>
        </header>

        <div className="mt-6 grid gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
          <aside className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.035)]">
            <h3 className="text-lg font-semibold text-white">Этапы анализа</h3>
            <div className="mt-5">
              {steps.map((step, index) => {
                const done = Boolean(step?.done)
                const isLast = index === steps.length - 1
                return (
                  <div key={step?.key || `learning-result-modal-step-${index}`} className="relative flex gap-4 pb-5 last:pb-0">
                    {!isLast ? <div className="absolute left-[15px] top-8 h-[calc(100%-24px)] w-px bg-emerald-300/38" /> : null}
                    <div className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm font-bold ${
                      done
                        ? 'border-emerald-300/65 bg-emerald-400/16 text-emerald-200 shadow-[0_0_18px_rgba(52,211,153,0.22)]'
                        : 'border-white/14 bg-white/[0.035] text-white/46'
                    }`}>
                      {done ? '✓' : index + 1}
                    </div>
                    <div className="min-w-0 pt-1">
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="text-base font-semibold text-emerald-300">{index + 1}</span>
                        <span className="min-w-0 text-sm font-semibold text-white/82">{getLearningText(step?.label, `Шаг ${index + 1}`)}</span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="mt-5 border-t border-white/10 pt-5">
              <div className="flex items-start gap-3 rounded-[18px] border border-emerald-300/14 bg-emerald-400/[0.055] px-3 py-3 text-sm leading-relaxed text-white/70">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-emerald-300/28 text-emerald-300">i</span>
                <span>{nextVersionText}</span>
              </div>
            </div>
          </aside>

          <section className="min-w-0 space-y-5">
            <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.035)]">
              <h3 className="text-lg font-semibold text-white">A. На основании каких данных сделан вывод</h3>
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <LearningEvidenceCard title="pH" metric={evidence?.ph} accent="cyan" icon="pH" />
                <LearningEvidenceCard title="EC" metric={evidence?.ec} accent="amber" icon="EC" />
                <LearningEvidenceCard title="Температура воздуха" metric={evidence?.air_temp} accent="violet" icon="°" />
                <LearningEvidenceCard title="Влажность" metric={evidence?.humidity} accent="emerald" icon="◌" />
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                <LearningEvidenceCounter title="pH Up:" value={evidence?.ph_up_doses ?? 0} suffix="микродозы" accent="cyan" icon="↑" />
                <LearningEvidenceCounter title="pH Down:" value={evidence?.ph_down_doses ?? 0} suffix="микродозы" accent="cyan" icon="↓" />
                <LearningEvidenceCounter title="EC ниже нормы:" value={evidence?.ec_alerts ?? 0} suffix="алертов" accent="amber" icon="⌁" />
                <LearningEvidenceCounter title="pH ниже нормы:" value={evidence?.ph_alerts ?? 0} suffix="алерта" accent="violet" icon="△" />
                <LearningEvidenceCounter title="Опросник:" value="урожай" suffix="пригоден" accent="emerald" icon="□" />
                <LearningEvidenceCounter title="Комментарий:" value="оператора" suffix="учтён" accent="emerald" icon="◯" />
              </div>
            </div>

            <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.035)]">
              <h3 className="text-lg font-semibold text-white">B. Вывод ИИ</h3>
              <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-white/72">
                {getLearningText(learningResult?.ai_conclusion, 'ИИ-анализ завершён, но текстовый вывод отсутствует.')}
              </p>
            </div>

            <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.035)]">
              <h3 className="text-lg font-semibold text-white">C. Что изменилось в АгроТехКарте</h3>
              <div className="mt-4">
                <LearningChangesTable changes={learningResult?.changes} />
              </div>
            </div>
          </section>
        </div>

        <footer className="mt-5 flex flex-col gap-3 border-t border-white/10 pt-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-start gap-3 text-sm leading-relaxed text-white/58">
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-white/16 text-white/60">i</span>
            <span>Отчёт включает телеметрию, алерты, pH-дозирование, опросник и вывод ИИ.</span>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              disabled
              className="min-h-[48px] rounded-[16px] border border-white/10 bg-white/[0.035] px-5 text-sm font-semibold text-white/42 disabled:cursor-not-allowed"
            >
              Скачать отчёт
            </button>
            <button
              type="button"
              onClick={() => console.log('Open new AgroTechCard', learningResult)}
              className="min-h-[48px] rounded-[16px] border border-violet-200/30 bg-gradient-to-r from-sky-500 to-fuchsia-600 px-5 text-sm font-semibold text-white shadow-[0_0_28px_rgba(168,85,247,0.28)] transition hover:brightness-110"
            >
              Открыть новую АгроТехКарту
            </button>
          </div>
        </footer>
      </div>
    </div>
  )
}

function formatGraphNumber(value, digits = 2) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return number.toFixed(digits).replace(/\.?0+$/, '')
}

function formatGraphFixed(value, digits = 2) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return number.toFixed(digits)
}

function toGraphNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function smoothPhPoints(points, alpha = 0.22) {
  if (!Array.isArray(points) || points.length < 3) return points

  let previousSmoothed = points[0].ph
  let previousRaw = points[0].ph
  return points.map((point, index) => {
    const currentPh = toGraphNumber(point?.ph)
    if (index === 0 || currentPh === null) {
      previousSmoothed = currentPh ?? previousSmoothed
      previousRaw = currentPh ?? previousRaw
      return point
    }

    const delta = Math.abs(currentPh - previousRaw)
    const effectiveAlpha = delta > 0.35 ? 0.55 : alpha
    const smoothed = effectiveAlpha * currentPh + (1 - effectiveAlpha) * previousSmoothed
    previousSmoothed = smoothed
    previousRaw = currentPh
    return {
      ...point,
      ph: smoothed,
    }
  })
}

const LIVE_RENDER_DELAY_MS = 2500
const LIVE_WINDOW_MS = 90000
const LIVE_RENDER_FPS_MS = 1000 / 30
const BUFFER_EXTRA_MS = 20000
const LIVE_BUFFER_LIMIT = 220

function clampGraphValue(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function normalizeGraphPoints(points) {
  if (!Array.isArray(points)) return []

  return points
    .map((point, index) => {
      const ph = toGraphNumber(point?.ph)
      const timestamp = Date.parse(point?.time)
      if (ph === null || !Number.isFinite(timestamp)) return null
      return {
        ...point,
        index,
        ph,
        timestamp,
      }
    })
    .filter(Boolean)
}

function formatGraphTimeLabel(timestamp) {
  if (!Number.isFinite(timestamp)) return ''

  return new Date(timestamp).toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function getInterpolatedPointAtTime(buffer, timestamp) {
  if (!Array.isArray(buffer) || buffer.length === 0 || !Number.isFinite(timestamp)) return null

  let previousPoint = null
  let nextPoint = null
  for (const point of buffer) {
    if (point.timestamp <= timestamp) {
      previousPoint = point
    } else {
      nextPoint = point
      break
    }
  }

  if (previousPoint && nextPoint && nextPoint.timestamp !== previousPoint.timestamp) {
    const ratio = clampGraphValue(
      (timestamp - previousPoint.timestamp) / (nextPoint.timestamp - previousPoint.timestamp),
      0,
      1,
    )
    return {
      ...previousPoint,
      time: new Date(timestamp).toISOString(),
      label: formatGraphTimeLabel(timestamp),
      timestamp,
      ph: previousPoint.ph + (nextPoint.ph - previousPoint.ph) * ratio,
      isVirtual: true,
    }
  }

  if (previousPoint) {
    return {
      ...previousPoint,
      time: new Date(timestamp).toISOString(),
      label: formatGraphTimeLabel(timestamp),
      timestamp,
      isVirtual: true,
    }
  }

  if (nextPoint) {
    return {
      ...nextPoint,
      time: new Date(timestamp).toISOString(),
      label: formatGraphTimeLabel(timestamp),
      timestamp,
      isVirtual: true,
    }
  }

  return null
}

function buildSmoothPath(points) {
  if (!Array.isArray(points) || points.length === 0) return ''
  if (points.length === 1) return `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`

  if (points.length === 2) {
    return `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)} L ${points[1].x.toFixed(1)} ${points[1].y.toFixed(1)}`
  }

  const midpoint = (from, to) => ({
    x: (from.x + to.x) / 2,
    y: (from.y + to.y) / 2,
  })
  let path = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`
  path += ` L ${midpoint(points[0], points[1]).x.toFixed(1)} ${midpoint(points[0], points[1]).y.toFixed(1)}`
  for (let index = 1; index < points.length - 1; index += 1) {
    const mid = midpoint(points[index], points[index + 1])
    path += ` Q ${points[index].x.toFixed(1)} ${points[index].y.toFixed(1)}, ${mid.x.toFixed(1)} ${mid.y.toFixed(1)}`
  }
  const last = points[points.length - 1]
  path += ` L ${last.x.toFixed(1)} ${last.y.toFixed(1)}`
  return path
}

function PhLiveChart({ data }) {
  const incomingPoints = useMemo(() => normalizeGraphPoints(data?.points), [data?.points])
  const isCycleMode = data?.mode === 'cycle' || Boolean(data?.cycle_id)
  const isLiveMode = !isCycleMode
  const rawBufferRef = useRef([])
  const [bufferVersion, setBufferVersion] = useState(0)
  const [renderClock, setRenderClock] = useState(Date.now())

  useEffect(() => {
    if (incomingPoints.length === 0) {
      rawBufferRef.current = []
      setBufferVersion((version) => version + 1)
      return
    }

    if (isCycleMode) {
      rawBufferRef.current = incomingPoints.slice(-LIVE_BUFFER_LIMIT)
      setBufferVersion((version) => version + 1)
      return
    }

    const mergedByTime = new Map(rawBufferRef.current.map((point) => [point.time || String(point.timestamp), point]))
    incomingPoints.forEach((point) => {
      mergedByTime.set(point.time || String(point.timestamp), point)
    })
    const merged = Array.from(mergedByTime.values()).sort((a, b) => a.timestamp - b.timestamp)
    const newestTimestamp = merged[merged.length - 1]?.timestamp ?? Date.now()
    const retentionStart = newestTimestamp - (LIVE_RENDER_DELAY_MS + LIVE_WINDOW_MS + BUFFER_EXTRA_MS)
    rawBufferRef.current = merged
      .filter((point) => point.timestamp >= retentionStart)
      .slice(-LIVE_BUFFER_LIMIT)
      .map((point, index) => ({ ...point, index }))
    setBufferVersion((version) => version + 1)
  }, [incomingPoints, isCycleMode])

  useEffect(() => {
    if (!isLiveMode) {
      setRenderClock(Date.now())
      return undefined
    }

    let frameId = null
    let lastUpdate = 0
    const tick = (now) => {
      if (now - lastUpdate >= LIVE_RENDER_FPS_MS) {
        setRenderClock(Date.now())
        lastUpdate = now
      }
      frameId = requestAnimationFrame(tick)
    }

    frameId = requestAnimationFrame(tick)
    return () => {
      if (frameId) cancelAnimationFrame(frameId)
    }
  }, [isLiveMode])

  const bufferedLivePoints = useMemo(() => rawBufferRef.current, [bufferVersion])
  const displayTime = renderClock - LIVE_RENDER_DELAY_MS
  const windowStart = displayTime - LIVE_WINDOW_MS
  const windowEnd = displayTime
  const points = useMemo(() => {
    if (!isLiveMode) {
      return incomingPoints.slice(-80).map((point, index) => ({ ...point, index }))
    }

    const leftBoundaryPoint = getInterpolatedPointAtTime(bufferedLivePoints, windowStart)
    const rightBoundaryPoint = getInterpolatedPointAtTime(bufferedLivePoints, displayTime)
    const displayPointsByTime = new Map()
    if (leftBoundaryPoint) {
      displayPointsByTime.set(String(leftBoundaryPoint.timestamp), leftBoundaryPoint)
    }
    bufferedLivePoints
      .filter((point) => point.timestamp > windowStart && point.timestamp < displayTime)
      .forEach((point) => {
        displayPointsByTime.set(String(point.timestamp), point)
      })

    if (rightBoundaryPoint) {
      displayPointsByTime.set(String(rightBoundaryPoint.timestamp), rightBoundaryPoint)
    }

    return Array.from(displayPointsByTime.values())
      .sort((a, b) => a.timestamp - b.timestamp)
      .map((point, index) => ({ ...point, index }))
  }, [bufferedLivePoints, displayTime, incomingPoints, isLiveMode, windowEnd, windowStart])
  const dosingEvents = useMemo(
    () => (Array.isArray(data?.dosing_events) ? data.dosing_events : []),
    [data?.dosing_events],
  )
  const visibleDosingEvents = dosingEvents.slice(-12)
  const targetPh = toGraphNumber(data?.target_ph)
  const targetMin = toGraphNumber(data?.target_min)
  const targetMax = toGraphNumber(data?.target_max)
  const values = (isLiveMode ? bufferedLivePoints : points).map((point) => point.ph)
  if (targetPh !== null) values.push(targetPh)
  if (targetMin !== null) values.push(targetMin)
  if (targetMax !== null) values.push(targetMax)
  const visualPoints = useMemo(() => smoothPhPoints(points), [points])

  if (points.length < 2) {
    return (
      <div className="flex h-[360px] items-center justify-center rounded-[22px] border border-white/[0.08] bg-white/[0.018] text-sm text-white/50">
        Пока нет pH-точек для построения графика.
      </div>
    )
  }

  const width = 920
  const height = 390
  const pad = { left: 50, right: 28, top: 34, bottom: 48 }
  const innerWidth = width - pad.left - pad.right
  const innerHeight = height - pad.top - pad.bottom
  const minValue = values.length ? Math.min(...values) : 5.5
  const maxValue = values.length ? Math.max(...values) : 7.3
  const liveBaseMin = 5.5
  const liveBaseMax = 7.3
  const yMin = isLiveMode && minValue >= liveBaseMin
    ? liveBaseMin
    : Math.max(3.5, Math.floor((minValue - 0.25) * 10) / 10)
  const yMax = isLiveMode && maxValue <= liveBaseMax
    ? liveBaseMax
    : Math.min(9, Math.ceil((maxValue + 0.25) * 10) / 10)
  const valueSpan = Math.max(0.2, yMax - yMin)
  const validTimes = points.map((point) => point.timestamp).filter(Number.isFinite)
  const minTime = isLiveMode ? windowStart : (validTimes.length > 1 ? Math.min(...validTimes) : null)
  const maxTime = isLiveMode ? windowEnd : (validTimes.length > 1 ? Math.max(...validTimes) : null)
  const timeSpan = minTime !== null && maxTime !== null ? Math.max(1, maxTime - minTime) : null
  const xForPoint = (point) => {
    if (timeSpan && Number.isFinite(point.timestamp)) {
      return pad.left + ((point.timestamp - minTime) / timeSpan) * innerWidth
    }
    return pad.left + (point.index / Math.max(1, points.length - 1)) * innerWidth
  }
  const yForValue = (value) => pad.top + ((yMax - value) / valueSpan) * innerHeight
  const chartPoints = visualPoints.map((point) => ({
    ...point,
    x: xForPoint(point),
    y: yForValue(point.ph),
  }))
  const linePath = buildSmoothPath(chartPoints)
  const baselineY = height - pad.bottom
  const areaPath = `${linePath} L ${chartPoints[chartPoints.length - 1].x.toFixed(1)} ${baselineY} L ${chartPoints[0].x.toFixed(1)} ${baselineY} Z`
  const gridValues = Array.from({ length: 4 }, (_, index) => yMin + (valueSpan * index) / 3)
  const xLabels = isLiveMode
    ? [
      { x: pad.left, label: formatGraphTimeLabel(windowStart) },
      { x: pad.left + innerWidth / 2, label: formatGraphTimeLabel(windowStart + LIVE_WINDOW_MS / 2) },
      { x: width - pad.right, label: formatGraphTimeLabel(windowEnd) },
    ]
    : Array.from(new Set([0, Math.floor((points.length - 1) / 2), points.length - 1])).map((index) => ({
      x: xForPoint(points[index]),
      label: points[index]?.label || '',
    }))
  const rawLastPoint = incomingPoints[incomingPoints.length - 1] || points[points.length - 1]
  const lastStatus = targetMin !== null && rawLastPoint.ph < targetMin
    ? 'below'
    : targetMax !== null && rawLastPoint.ph > targetMax
      ? 'above'
      : 'ok'
  const markerSourcePoints = isLiveMode ? bufferedLivePoints : points
  const eventMarkers = visibleDosingEvents.map((event, index) => {
    const eventTime = Date.parse(event?.time)
    if (isLiveMode && (!Number.isFinite(eventTime) || eventTime < windowStart || eventTime > windowEnd)) return null
    const nearestPoint = Number.isFinite(eventTime) && markerSourcePoints.length
      ? markerSourcePoints.reduce((best, point) => (
        Math.abs(point.timestamp - eventTime) < Math.abs(best.timestamp - eventTime) ? point : best
      ), markerSourcePoints[0])
      : markerSourcePoints[Math.min(index, markerSourcePoints.length - 1)]
    const eventValue = nearestPoint?.ph ?? toGraphNumber(event?.current_ph) ?? rawLastPoint.ph
    const rawX = Number.isFinite(eventTime) && timeSpan
      ? pad.left + ((eventTime - minTime) / timeSpan) * innerWidth
      : xForPoint(nearestPoint)
    return {
      key: `${event?.time || index}-${event?.pump_id || 'dose'}`,
      x: clampGraphValue(rawX, pad.left + 12, width - pad.right - 12),
      y: clampGraphValue(yForValue(eventValue), pad.top + 14, height - pad.bottom - 14),
      pumpId: event?.pump_id,
      label: event?.label || '',
    }
  }).filter(Boolean)
  return (
    <div className="overflow-hidden rounded-[24px] border border-white/[0.08] bg-slate-950/20 px-2 py-3">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full">
        <defs>
          <linearGradient id="phLineGradient" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#5fb8d3" />
            <stop offset="100%" stopColor="#8fc7df" />
          </linearGradient>
          <linearGradient id="phAreaGradient" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="rgba(95,184,211,0.08)" />
            <stop offset="55%" stopColor="rgba(95,184,211,0.025)" />
            <stop offset="100%" stopColor="rgba(56,189,248,0)" />
          </linearGradient>
          <linearGradient id="phTargetZoneGradient" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="rgba(45,212,191,0.055)" />
            <stop offset="50%" stopColor="rgba(52,211,153,0.045)" />
            <stop offset="100%" stopColor="rgba(45,212,191,0.055)" />
          </linearGradient>
          <clipPath id="phChartClip">
            <rect x={pad.left} y={pad.top} width={innerWidth} height={innerHeight} />
          </clipPath>
        </defs>

        {gridValues.map((value) => {
          const y = yForValue(value)
          return (
            <g key={`grid-${value}`}>
              <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke="rgba(255,255,255,0.055)" />
              <text x={pad.left - 14} y={y + 4} textAnchor="end" className="fill-white/36 text-[11px]">
                {formatGraphNumber(value, 1)}
              </text>
            </g>
          )
        })}

        {targetMin !== null && targetMax !== null ? (
          <rect
            x={pad.left}
            y={yForValue(targetMax)}
            width={innerWidth}
            height={Math.max(2, yForValue(targetMin) - yForValue(targetMax))}
            rx="18"
            fill="url(#phTargetZoneGradient)"
          />
        ) : null}

        <path d={areaPath} fill="url(#phAreaGradient)" clipPath="url(#phChartClip)" />

        {targetPh !== null ? (
          <line
            x1={pad.left}
            x2={width - pad.right}
            y1={yForValue(targetPh)}
            y2={yForValue(targetPh)}
            stroke="rgba(180,170,215,0.46)"
            strokeDasharray="7 9"
            strokeWidth="1.5"
          />
        ) : null}

        <path d={linePath} fill="none" stroke="url(#phLineGradient)" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" clipPath="url(#phChartClip)" />

        <g clipPath="url(#phChartClip)">
          {eventMarkers.map((marker) => (
            <g key={marker.key} transform={`translate(${marker.x} ${marker.y})`}>
              <circle
                r="8"
                fill={marker.pumpId === 'ph_down' ? 'rgba(251,146,60,0.16)' : 'rgba(125,160,220,0.18)'}
                stroke={marker.pumpId === 'ph_down' ? 'rgba(251,146,60,0.50)' : 'rgba(147,197,253,0.48)'}
                strokeWidth="1.2"
              />
              <text
                y="4"
                textAnchor="middle"
                className={marker.pumpId === 'ph_down' ? 'fill-orange-100 text-[11px] font-bold' : 'fill-blue-100 text-[11px] font-bold'}
              >
                {marker.pumpId === 'ph_down' ? '↓' : '↑'}
              </text>
            </g>
          ))}
        </g>

        {xLabels.map((tick, index) => (
          <text key={`x-${index}`} x={tick.x} y={height - 18} textAnchor="middle" className="fill-white/34 text-[11px]">
            {tick.label || ''}
          </text>
        ))}
      </svg>

      {lastStatus !== 'ok' ? (
        <div className="mt-3 inline-flex rounded-full border border-amber-300/16 bg-amber-300/[0.075] px-3 py-1 text-xs font-semibold text-amber-100/90">
          pH {lastStatus === 'below' ? 'ниже' : 'выше'} диапазона удержания
        </div>
      ) : null}
    </div>
  )
}

function PhGraphsView({
  data,
  loading,
  error,
  graphCycleId,
  onLiveClick,
  onReload,
}) {
  const points = Array.isArray(data?.points) ? data.points : []
  const dosingEvents = Array.isArray(data?.dosing_events) ? data.dosing_events : []
  const summary = data?.summary || {}
  const dosingChannels = data?.dosing_channels || {}
  const channels = dosingChannels.channels || dosingChannels
  const phUpConnected = Boolean(channels.ph_up?.connected)
  const phDownConnected = Boolean(channels.ph_down?.connected)
  const anyDosingConnected = Boolean(dosingChannels.any_connected)
  const hasStaleDosingChannel = [channels.ph_up?.status, channels.ph_down?.status].includes('stale')
  const lastPoint = points[points.length - 1]
  const targetText = data?.target_ph === null || data?.target_ph === undefined
    ? 'Целевой pH не задан.'
    : formatGraphNumber(data.target_ph)
  const rangeText = data?.target_min === null || data?.target_min === undefined || data?.target_max === null || data?.target_max === undefined
    ? 'Целевой pH не задан.'
    : `${formatGraphNumber(data.target_min)}–${formatGraphNumber(data.target_max)}`
  const phUp = summary.ph_up_doses ?? 0
  const phDown = summary.ph_down_doses ?? 0
  const dosingSummaryValue = anyDosingConnected ? `${phUp} / ${phDown}` : 'ожидание ESP32'
  const dosingSummaryHint = anyDosingConnected
    ? (dosingEvents.length ? 'подключённые каналы' : 'доз пока нет')
    : hasStaleDosingChannel
      ? 'статус дозаторов устарел'
      : 'каналы не подключены'

  const statCards = [
    {
      label: 'Последний pH',
      value: formatGraphFixed(lastPoint?.ph),
      hint: points.length ? `${points.length} точек` : 'нет данных',
      icon: '∿',
      accent: 'text-cyan-100',
      shell: 'from-cyan-300/[0.11] to-slate-950/0',
    },
    {
      label: 'Целевой pH',
      value: targetText,
      hint: data?.tolerance ? `±${formatGraphNumber(data.tolerance)}` : 'Целевой pH не задан.',
      icon: '◎',
      accent: 'text-violet-100',
      shell: 'from-violet-300/[0.10] to-slate-950/0',
    },
    {
      label: 'Диапазон удержания',
      value: rangeText,
      hint: data?.target_min !== null && data?.target_min !== undefined ? 'зона допуска' : 'Целевой диапазон не задан',
      icon: '◌',
      accent: 'text-emerald-100',
      shell: 'from-emerald-300/[0.10] to-slate-950/0',
    },
    {
      label: 'pH Up / pH Down',
      value: dosingSummaryValue,
      hint: dosingSummaryHint,
      icon: '↕',
      accent: 'text-fuchsia-100',
      shell: 'from-fuchsia-300/[0.09] to-slate-950/0',
    },
  ]

  return (
    <div className="custom-scrollbar flex min-w-0 max-w-full flex-col gap-4 min-[1700px]:h-full min-[1700px]:min-h-0 min-[1700px]:overflow-y-auto min-[1700px]:pr-1">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[24px] font-semibold tracking-tight text-white md:text-[28px]">Графики цикла</div>
          <p className="mt-1.5 text-sm text-white/62">Динамика pH, целевой диапазон и события дозирования.</p>
        </div>
        <div className="flex items-center gap-2">
          {graphCycleId ? (
            <span className="rounded-full border border-violet-300/18 bg-violet-300/[0.08] px-3 py-1.5 text-xs font-semibold text-violet-100/90">
              DEMO cycle #{graphCycleId}
            </span>
          ) : (
            <span className="rounded-full border border-emerald-300/16 bg-emerald-300/[0.075] px-3 py-1.5 text-xs font-semibold text-emerald-100/90">
              LIVE
            </span>
          )}
          <button
            type="button"
            onClick={onLiveClick}
            className={`h-8 rounded-xl border px-3 text-xs font-semibold transition ${
              graphCycleId
                ? 'border-cyan-200/18 bg-cyan-300/[0.08] text-cyan-100 hover:bg-cyan-300/[0.12]'
                : 'border-emerald-200/18 bg-emerald-300/[0.08] text-emerald-100'
            }`}
          >
            {graphCycleId ? 'Вернуться в Live' : 'Текущий цикл'}
          </button>
          <button
            type="button"
            onClick={onReload}
            className="h-8 rounded-xl border border-white/10 bg-white/[0.035] px-3 text-xs font-semibold text-white/64 transition hover:bg-white/[0.07] hover:text-white"
          >
            Обновить
          </button>
        </div>
      </div>

      <div className="grid min-w-0 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {statCards.map((card) => (
          <GlassCard key={card.label} className={`rounded-[22px] border-white/[0.08] bg-gradient-to-br ${card.shell}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-white/36">{card.label}</div>
                <div className={`mt-3 truncate text-[25px] font-semibold leading-none ${card.accent}`}>{card.value}</div>
                <div className="mt-2 truncate text-xs text-white/42">{card.hint}</div>
              </div>
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.035] text-sm font-semibold text-white/50">
                {card.icon}
              </div>
            </div>
          </GlassCard>
        ))}
      </div>

      <GlassCard className="relative min-h-[520px] rounded-[28px] border-white/[0.08] bg-white/[0.018]">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-[20px] font-semibold text-white">{graphCycleId ? 'pH цикла' : 'Live pH раствора'}</div>
            <p className="mt-1 text-sm text-white/52">
              {graphCycleId ? 'Исторические данные завершённого цикла.' : 'Данные обновляются каждые 2 секунды в live-режиме.'}
            </p>
          </div>
          <div className={`rounded-full border px-3 py-1 text-xs font-semibold ${
            data?.mode === 'cycle'
              ? 'border-violet-300/18 bg-violet-300/[0.08] text-violet-100/86'
              : 'border-emerald-300/16 bg-emerald-300/[0.075] text-emerald-100/86'
          }`}>
            {data?.mode === 'cycle' ? `DEMO cycle #${graphCycleId || data?.cycle_id || ''}` : 'LIVE'}
          </div>
        </div>

        {error ? (
          <div className="mb-3 rounded-2xl border border-amber-300/16 bg-amber-300/[0.075] px-4 py-3 text-sm text-amber-100/90">{error}</div>
        ) : null}
        {loading && !data ? (
          <div className="flex h-[390px] items-center justify-center rounded-[24px] border border-white/[0.08] bg-white/[0.018]">
            <div className="text-center">
              <div className="mx-auto mb-3 h-2 w-40 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full w-1/2 animate-pulse rounded-full bg-cyan-200/35" />
              </div>
              <div className="text-sm text-white/50">Загружаем pH-график...</div>
            </div>
          </div>
        ) : (
          <PhLiveChart data={data} />
        )}

        <div className="mt-4 flex flex-wrap gap-2 text-xs text-white/54">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.025] px-3 py-1"><span className="h-1.5 w-5 rounded-full bg-cyan-300/70" />pH</span>
          <span className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.025] px-3 py-1"><span className="h-0.5 w-5 border-t border-dashed border-violet-300/70" />целевой pH</span>
          <span className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.025] px-3 py-1"><span className="h-2.5 w-5 rounded bg-emerald-300/14" />зона допуска</span>
          {phUpConnected ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.025] px-3 py-1"><span className="flex h-4 w-4 items-center justify-center rounded-full border border-blue-200/24 bg-blue-300/10 text-[10px] text-blue-100">↑</span>pH Up</span>
          ) : null}
          {phDownConnected ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.025] px-3 py-1"><span className="flex h-4 w-4 items-center justify-center rounded-full border border-orange-200/24 bg-orange-300/10 text-[10px] text-orange-100">↓</span>pH Down</span>
          ) : null}
          {!anyDosingConnected ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-white/[0.07] bg-white/[0.018] px-3 py-1 text-white/36">дозаторы: ожидание ESP32</span>
          ) : null}
        </div>

        {!anyDosingConnected ? (
          <div className="mt-3 max-w-2xl text-xs leading-5 text-white/38">
            {hasStaleDosingChannel
              ? 'Статус дозаторов устарел, маркеры временно скрыты.'
              : 'Дозаторы pH Up / pH Down ожидают подключения ESP32. Маркеры дозирования появятся после подключения каналов.'}
          </div>
        ) : null}

        {data && data.target_ph === null ? (
          <div className="mt-3 text-xs text-white/38">Целевой диапазон не задан.</div>
        ) : null}
        {data && dosingEvents.length === 0 ? (
          <div className="mt-1 text-xs text-white/38">Событий дозирования пока нет.</div>
        ) : null}
      </GlassCard>
    </div>
  )
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
  const [crops, setCrops] = useState([])
  const [selectedCropSlug, setSelectedCropSlug] = useState('')
  const [selectedDemoCropSlug, setSelectedDemoCropSlug] = useState('mint')
  const [demoLearningLoading, setDemoLearningLoading] = useState(false)
  const [demoLearningError, setDemoLearningError] = useState('')
  const [cropsLoading, setCropsLoading] = useState(true)
  const [cropsError, setCropsError] = useState('')
  const [currentCycle, setCurrentCycle] = useState(null)
  const [lastFinishedCycle, setLastFinishedCycle] = useState(null)
  const [learningStatus, setLearningStatus] = useState(null)
  const [learningResult, setLearningResult] = useState(null)
  const [learningResultError, setLearningResultError] = useState('')
  const [learningTargetStatus, setLearningTargetStatus] = useState(null)
  const [visualLearningStatus, setVisualLearningStatus] = useState(null)
  const [learningStatusError, setLearningStatusError] = useState('')
  const [learningWidgetOpen, setLearningWidgetOpen] = useState(false)
  const [learningModalOpen, setLearningModalOpen] = useState(false)
  const learningVisualTimerRef = useRef(null)
  const learningResultInitialCycleRef = useRef(null)
  const learningResultFinalCycleRef = useRef(null)
  const [isCycleLoading, setIsCycleLoading] = useState(false)
  const [cycleError, setCycleError] = useState('')
  const [isFinishCycleModalOpen, setIsFinishCycleModalOpen] = useState(false)
  const [finishCycleForm, setFinishCycleForm] = useState(createInitialFinishCycleForm)
  const [finishCycleError, setFinishCycleError] = useState('')
  const [phTargetForm, setPhTargetForm] = useState(PH_TARGET_INITIAL_FORM)
  const [phTargetLoading, setPhTargetLoading] = useState(false)
  const [phTargetSaving, setPhTargetSaving] = useState(false)
  const [phTargetMessage, setPhTargetMessage] = useState('')
  const [phTargetError, setPhTargetError] = useState('')
  const [phTargetConfigured, setPhTargetConfigured] = useState(false)
  const [phGraphData, setPhGraphData] = useState(null)
  const [phGraphLoading, setPhGraphLoading] = useState(false)
  const [phGraphError, setPhGraphError] = useState('')
  const [graphCycleId, setGraphCycleId] = useState(null)

  const pushThought = () => undefined

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
        const data = await requestJson('/api/system-feed?limit=15')
        if (!isMounted || !Array.isArray(data)) return

        setThoughts(
          data.map((entry) => ({
            id: entry.id ?? makeId(),
            text: entry.text || 'Системное событие',
            time: entry.time || formatTimestampLabel(entry.created_at),
          }))
        )
      } catch (error) {
        console.error('Failed to load system feed', error)
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

  const applyPhTargetSettings = (settings) => {
    const isConfigured = Boolean(settings?.is_configured)
    setPhTargetConfigured(isConfigured)
    setPhTargetForm({
      targetPh: settings?.is_configured && settings.target_ph !== null && settings.target_ph !== undefined
        ? String(settings.target_ph)
        : '',
      tolerance: settings?.is_configured && settings.tolerance !== null && settings.tolerance !== undefined
        ? String(settings.tolerance)
        : PH_TARGET_INITIAL_FORM.tolerance,
      autodosingEnabled: Boolean(settings?.autodosing_enabled),
    })
  }

  const loadPhTargetSettings = async () => {
    setPhTargetLoading(true)
    setPhTargetError('')
    setPhTargetMessage('')
    try {
      const settings = await requestJson(`/api/ph-target-settings/current?tray_id=${DEFAULT_TRAY_ID}`)
      applyPhTargetSettings(settings)
      return settings
    } catch (error) {
      console.error('Failed to load pH target settings', error)
      applyPhTargetSettings(null)
      if (error.status !== 404) {
        setPhTargetError('Не удалось загрузить целевой pH.')
      }
      return null
    } finally {
      setPhTargetLoading(false)
    }
  }

  const loadLearningStatus = useCallback(async (cycleId) => {
    if (!cycleId) return null
    try {
      const status = await requestJson(`/api/cycles/${cycleId}/learning-status`)
      setLearningStatus(status)
      setLearningTargetStatus(status)
      setLearningStatusError('')
      return status
    } catch (error) {
      console.error('Failed to load learning status', error)
      setLearningStatusError('Не удалось загрузить статус обучения')
      return null
    }
  }, [])

  const loadLearningResult = useCallback(async (cycleId) => {
    if (!cycleId) return null

    try {
      const result = await requestJson(`/api/cycles/${cycleId}/learning-result`)
      setLearningResult(result)
      setLearningResultError('')
      return result
    } catch (error) {
      console.error('Failed to load learning result', error)
      setLearningResult(null)
      setLearningResultError('Не удалось загрузить результат обучения')
      return null
    }
  }, [])

  const loadPhGraphData = useCallback(async ({ cycleId = null } = {}) => {
    setPhGraphLoading(true)
    setPhGraphError('')
    try {
      const path = cycleId
        ? `/api/charts/ph-live?cycle_id=${encodeURIComponent(cycleId)}`
        : `/api/charts/ph-live?tray_id=${encodeURIComponent(DEFAULT_TRAY_ID)}`
      const data = await requestJson(path)
      setPhGraphData(data)
      return data
    } catch (error) {
      console.error('Failed to load pH graph', error)
      setPhGraphError(getErrorMessage(error, 'Не удалось загрузить pH-график'))
      setPhGraphData(null)
      return null
    } finally {
      setPhGraphLoading(false)
    }
  }, [])

  const triggerLearningPipeline = (cycleId) => {
    if (!cycleId) return
    void requestJson(`/api/cycles/${cycleId}/learning-pipeline`, {
      method: 'POST',
    })
      .then((pipelineResult) => {
        if (pipelineResult?.status === 'failed') {
          setLearningStatusError('Не удалось запустить анализ обучения')
        }
        void loadLearningStatus(cycleId)
      })
      .catch((error) => {
        console.error('Failed to trigger learning pipeline', error)
        setLearningStatusError('Не удалось запустить анализ обучения')
      })
  }

  const loadCrops = async () => {
    setCropsLoading(true)
    setCropsError('')
    try {
      const cropsData = await requestJson('/api/crops')
      const normalizedCrops = Array.isArray(cropsData)
        ? cropsData.map(normalizeCrop).filter((crop) => crop.slug)
        : []

      setCrops(normalizedCrops)
      setSelectedCropSlug((prev) => (
        normalizedCrops.some((crop) => crop.slug === prev)
          ? prev
          : normalizedCrops[0]?.slug || ''
      ))
      return normalizedCrops
    } catch (error) {
      console.error('Failed to load crops', error)
      setCrops([])
      setSelectedCropSlug('')
      setCropsError('Не удалось загрузить культуры из базы данных')
      return null
    } finally {
      setCropsLoading(false)
    }
  }

  const demoCropOptions = useMemo(
    () => (crops.length > 0 ? crops : DEMO_CROP_FALLBACK),
    [crops],
  )

  useEffect(() => {
    if (!DEV_FEATURES_ENABLED) return

    setSelectedDemoCropSlug((prev) => (
      demoCropOptions.some((crop) => crop.slug === prev)
        ? prev
        : demoCropOptions[0]?.slug || 'mint'
    ))
  }, [demoCropOptions])

  const handleCreateDemoLearningResult = async () => {
    if (!DEV_FEATURES_ENABLED || demoLearningLoading) return

    const cropSlug = selectedDemoCropSlug || demoCropOptions[0]?.slug || 'mint'
    setDemoLearningLoading(true)
    setDemoLearningError('')
    try {
      const response = await requestJson(
        `/api/dev/learning-result-demo?crop_slug=${encodeURIComponent(cropSlug)}`,
        { method: 'POST' },
      )
      const cycleId = response?.cycle_id
      let result = response?.learning_result && typeof response.learning_result === 'object'
        ? response.learning_result
        : null

      if (!result && cycleId) {
        result = await loadLearningResult(cycleId)
      }
      if (!result) {
        throw new Error('Empty demo learning result')
      }

      if (cycleId) {
        learningResultInitialCycleRef.current = cycleId
        learningResultFinalCycleRef.current = cycleId
        setGraphCycleId(cycleId)
        setLastFinishedCycle({
          id: cycleId,
          crop_slug: response?.crop_slug || result.crop_slug || cropSlug,
        })
        void loadPhGraphData({ cycleId })
      }
      setLearningResult(result)
      setLearningResultError('')
      setLearningStatus(null)
      setLearningTargetStatus(null)
      setVisualLearningStatus(null)
      setLearningWidgetOpen(true)
      setMode('graphs')
    } catch (error) {
      console.error('Failed to create demo learning result', error)
      setDemoLearningError(getErrorMessage(error, 'DEMO недоступен'))
    } finally {
      setDemoLearningLoading(false)
    }
  }

  useEffect(() => {
    let isMounted = true

    const loadCycleData = async () => {
      setIsCycleLoading(true)
      try {
        const [, cycleData] = await Promise.all([
          loadCrops(),
          requestJson(`/api/cycles/current?tray_id=${DEFAULT_TRAY_ID}`),
        ])

        if (!isMounted) return

        setCurrentCycle(cycleData || null)
        setCycleError('')
      } catch (error) {
        console.error('Failed to load cycle data', error)
        if (!isMounted) return

        setCycleError('Не удалось загрузить данные активного цикла. Проверьте backend.')
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
    if (mode !== 'graphs') return undefined

    void loadPhGraphData({ cycleId: graphCycleId })
    if (graphCycleId) return undefined

    const graphPoller = setInterval(() => {
      void loadPhGraphData({ cycleId: null })
    }, TELEMETRY_POLL_INTERVAL_MS)

    return () => clearInterval(graphPoller)
  }, [mode, graphCycleId, loadPhGraphData])

  useEffect(() => {
    if (!currentCycle) {
      setPhTargetForm(PH_TARGET_INITIAL_FORM)
      setPhTargetLoading(false)
      setPhTargetSaving(false)
      setPhTargetMessage('')
      setPhTargetError('')
      setPhTargetConfigured(false)
      return
    }

    loadPhTargetSettings()
  }, [currentCycle?.id])

  useEffect(() => {
    const cycleId = lastFinishedCycle?.id
    if (!cycleId) {
      setLearningStatus(null)
      setLearningResult(null)
      setLearningTargetStatus(null)
      setVisualLearningStatus(null)
      setLearningStatusError('')
      setLearningResultError('')
      learningResultInitialCycleRef.current = null
      learningResultFinalCycleRef.current = null
      return undefined
    }

    let isMounted = true
    if (learningResultInitialCycleRef.current !== cycleId) {
      learningResultInitialCycleRef.current = cycleId
      learningResultFinalCycleRef.current = null
      void loadLearningResult(cycleId)
    }

    const pollLearningStatus = async () => {
      const status = await loadLearningStatus(cycleId)
      if (!isMounted) return null
      if (['completed', 'failed'].includes(status?.status) && learningResultFinalCycleRef.current !== cycleId) {
        learningResultFinalCycleRef.current = cycleId
        void loadLearningResult(cycleId)
      }
      return status
    }

    void pollLearningStatus()

    if (['completed', 'failed'].includes(learningStatus?.status)) {
      if (learningResultFinalCycleRef.current !== cycleId) {
        learningResultFinalCycleRef.current = cycleId
        void loadLearningResult(cycleId)
      }
      return () => {
        isMounted = false
      }
    }

    const learningPoller = setInterval(() => {
      void pollLearningStatus()
    }, LEARNING_POLL_INTERVAL_MS)

    return () => {
      isMounted = false
      clearInterval(learningPoller)
    }
  }, [lastFinishedCycle?.id, learningStatus?.status, loadLearningStatus, loadLearningResult])

  useEffect(() => {
    if (learningVisualTimerRef.current) {
      clearTimeout(learningVisualTimerRef.current)
      learningVisualTimerRef.current = null
    }

    if (!lastFinishedCycle?.id || !learningTargetStatus) {
      return undefined
    }

    const visualIndex = getVisualLearningStepIndex(visualLearningStatus)
    const targetIndex = getLearningTargetStepIndex(learningTargetStatus)
    const lastStepIndex = LEARNING_STEP_KEYS.length - 1

    const scheduleVisualUpdate = (nextStatus) => {
      learningVisualTimerRef.current = setTimeout(() => {
        setVisualLearningStatus(nextStatus)
        learningVisualTimerRef.current = null
      }, LEARNING_VISUAL_STEP_MS)
    }

    if (!visualLearningStatus) {
      setVisualLearningStatus(buildVisualLearningStatus(learningTargetStatus, 0))
      return undefined
    }

    if (learningTargetStatus.status === 'completed') {
      if (visualIndex < lastStepIndex) {
        scheduleVisualUpdate(buildVisualLearningStatus(learningTargetStatus, visualIndex + 1))
      } else if (visualLearningStatus.status !== 'completed') {
        scheduleVisualUpdate(buildFinalVisualLearningStatus(learningTargetStatus))
      }
    } else if (learningTargetStatus.status === 'failed') {
      const failedIndex = targetIndex >= 0 ? targetIndex : 0
      if (visualIndex < failedIndex) {
        scheduleVisualUpdate(buildVisualLearningStatus(learningTargetStatus, visualIndex + 1))
      } else if (visualLearningStatus.status !== 'failed') {
        scheduleVisualUpdate(buildVisualLearningStatus(learningTargetStatus, failedIndex, 'failed'))
      }
    } else if (learningTargetStatus.status === 'running') {
      if (visualIndex < targetIndex) {
        scheduleVisualUpdate(buildVisualLearningStatus(learningTargetStatus, visualIndex + 1))
      }
    } else if (learningTargetStatus.status === 'idle' && visualLearningStatus.status !== 'idle') {
      setVisualLearningStatus(learningTargetStatus)
    }

    return () => {
      if (learningVisualTimerRef.current) {
        clearTimeout(learningVisualTimerRef.current)
        learningVisualTimerRef.current = null
      }
    }
  }, [
    lastFinishedCycle?.id,
    learningTargetStatus,
    visualLearningStatus,
  ])

  const canOpenLearningDetails = Boolean(learningResult?.can_open_details && learningResult?.has_changes)

  useEffect(() => {
    if (learningModalOpen && !canOpenLearningDetails) {
      setLearningModalOpen(false)
    }
  }, [learningModalOpen, canOpenLearningDetails])

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

  const metricNormLabels = useMemo(
    () => buildMetricNormLabels(currentCycle),
    [currentCycle],
  )

  const metricsList = useMemo(
    () => [
      {
        title: 'Температура воды',
        value: formatMetricValue(metrics.waterTemp, 1),
        unit: '°C',
        norm: metricNormLabels.waterTemp,
        color: '#2CB4FF',
        values: sparklineSeries.waterTemp,
        icon: <DropletIcon className="h-6 w-6" />,
      },
      {
        title: 'Влажность воздуха',
        value: formatMetricValue(metrics.airHumidity, 1),
        unit: '%',
        norm: metricNormLabels.airHumidity,
        color: '#71F16A',
        values: sparklineSeries.airHumidity,
        icon: <HumidityIcon className="h-6 w-6" />,
      },
      {
        title: 'Температура воздуха',
        value: formatMetricValue(metrics.airTemp, 1),
        unit: '°C',
        norm: metricNormLabels.airTemp,
        color: '#C668FF',
        values: sparklineSeries.airTemp,
        icon: <ThermometerIcon className="h-6 w-6" />,
      },
      {
        title: 'pH',
        value: formatMetricValue(metrics.ph, 1),
        unit: '',
        norm: metricNormLabels.ph,
        color: '#7DD3FC',
        values: sparklineSeries.ph,
        icon: <PhIcon className="h-6 w-6" />,
      },
      {
        title: 'EC',
        value: formatMetricValue(metrics.ec, 2),
        unit: 'mS/cm',
        norm: metricNormLabels.ec,
        color: '#F7C948',
        values: sparklineSeries.ec,
        icon: <EcIcon className="h-6 w-6" />,
      },
    ],
    [metrics, metricNormLabels],
  )

  const selectedCrop = useMemo(
    () => crops.find((crop) => crop.slug === selectedCropSlug) || crops[0] || null,
    [crops, selectedCropSlug],
  )
  const currentLearningStatus = learningStatus?.status || (lastFinishedCycle ? 'running' : 'idle')
  const isSelectedCropLearningBlocked = Boolean(
    lastFinishedCycle &&
    selectedCropSlug &&
    selectedCropSlug === lastFinishedCycle.crop_slug &&
    !['completed', 'failed'].includes(currentLearningStatus),
  )

  const phTargetRange = useMemo(() => {
    if (!currentCycle) return null
    const target = Number(phTargetForm.targetPh)
    const tolerance = Number(phTargetForm.tolerance)
    if (
      !Number.isFinite(target)
      || target < 3.5
      || target > 9.0
      || !Number.isFinite(tolerance)
      || tolerance < 0.1
      || tolerance > 0.5
    ) return null
    return {
      min: target - tolerance,
      max: target + tolerance,
    }
  }, [currentCycle, phTargetForm.targetPh, phTargetForm.tolerance])

  const isPhTargetValid = useMemo(() => {
    const target = Number(phTargetForm.targetPh)
    const tolerance = Number(phTargetForm.tolerance)
    return (
      Number.isFinite(target)
      && target >= 3.5
      && target <= 9.0
      && Number.isFinite(tolerance)
      && tolerance >= 0.1
      && tolerance <= 0.5
    )
  }, [phTargetForm.targetPh, phTargetForm.tolerance])

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

  const handlePhTargetFieldChange = (field) => (event) => {
    const value = event.target.value
    setPhTargetMessage('')
    setPhTargetError('')
    setPhTargetForm((prev) => ({
      ...prev,
      [field]: value,
    }))
  }

  const handleSavePhTarget = async () => {
    if (!currentCycle || phTargetSaving) return

    const target = Number(phTargetForm.targetPh)
    const tolerance = Number(phTargetForm.tolerance)
    if (
      !Number.isFinite(target)
      || target < 3.5
      || target > 9.0
      || !Number.isFinite(tolerance)
      || tolerance < 0.1
      || tolerance > 0.5
    ) {
      setPhTargetMessage('')
      setPhTargetError('Проверьте целевой pH и допуск.')
      return
    }

    setPhTargetSaving(true)
    setPhTargetMessage('')
    setPhTargetError('')
    try {
      const settings = await requestJson('/api/ph-target-settings/current', {
        method: 'PUT',
        body: JSON.stringify({
          tray_id: DEFAULT_TRAY_ID,
          target_ph: target,
          tolerance,
          autodosing_enabled: true,
          source: 'manual',
        }),
      })
      applyPhTargetSettings(settings)
      setPhTargetMessage('Целевой pH сохранён.')
    } catch (error) {
      console.error('Failed to save pH target settings', error)
      setPhTargetError('Не удалось сохранить целевой pH.')
    } finally {
      setPhTargetSaving(false)
    }
  }

  const handleStartCycle = async () => {
    if (currentCycle) return
    if (cropsLoading) {
      setCycleError('Дождитесь загрузки культур из базы данных.')
      return
    }
    if (cropsError) {
      setCycleError('Не удалось загрузить культуры из базы данных. Повторите загрузку перед стартом цикла.')
      return
    }
    if (!selectedCropSlug || !selectedCrop) {
      setCycleError('Выберите культуру из базы данных перед стартом цикла.')
      return
    }
    if (isSelectedCropLearningBlocked) {
      setCycleError('Для этой культуры ещё обновляется АгроТехКарта после предыдущего цикла.')
      return
    }

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

  const handleOpenFinishCycleModal = () => {
    if (!currentCycle) return
    setFinishCycleForm(createInitialFinishCycleForm())
    setFinishCycleError('')
    setCycleError('')
    setIsFinishCycleModalOpen(true)
  }

  const handleCloseFinishCycleModal = () => {
    if (isCycleLoading) return
    setIsFinishCycleModalOpen(false)
    setFinishCycleError('')
  }

  const handleSubmitFinishCycle = async (event) => {
    event.preventDefault()
    if (!currentCycle) return

    if (!hasSelectedRequiredFinishCycleFields(finishCycleForm)) {
      setFinishCycleError('Заполните обязательные поля итогового опросника перед завершением цикла.')
      return
    }

    const trimmedMass = String(finishCycleForm.harvest_mass_grams || '').trim()
    const harvestMass = trimmedMass === '' ? null : Number(trimmedMass)

    if (harvestMass !== null && (!Number.isFinite(harvestMass) || harvestMass < 0)) {
      setFinishCycleError('Укажите неотрицательную массу урожая или оставьте поле пустым.')
      return
    }

    setIsCycleLoading(true)
    setCycleError('')
    setFinishCycleError('')
    try {
      const finished = await requestJson('/api/cycles/end', {
        method: 'POST',
        body: JSON.stringify({
          tray_id: currentCycle.tray_id || DEFAULT_TRAY_ID,
          harvest_status: finishCycleForm.harvest_status,
          harvest_mass_grams: harvestMass,
          completion_reason: finishCycleForm.completion_reason,
          problem_severity: finishCycleForm.problem_severity,
          problem_phase: finishCycleForm.problem_phase,
          plant_appearance: finishCycleForm.plant_appearance,
          cycle_problems: finishCycleForm.cycle_problems,
          manual_actions: finishCycleForm.manual_actions,
          followed_ai_advice: finishCycleForm.followed_ai_advice,
          ai_advice_helpfulness: finishCycleForm.ai_advice_helpfulness,
          operator_comment: finishCycleForm.operator_comment.trim() || null,
        }),
      })
      setIsFinishCycleModalOpen(false)
      setFinishCycleForm(createInitialFinishCycleForm())
      const finishedCycle = finished?.cycle || currentCycle
      setLastFinishedCycle(finishedCycle)
      const initialLearningStatus = {
        cycle_id: finishedCycle?.id,
        tray_id: finishedCycle?.tray_id || DEFAULT_TRAY_ID,
        crop_slug: finishedCycle?.crop_slug,
        crop_name_ru: finishedCycle?.crop_name_ru,
        status: 'running',
        current_step: 'questionnaire_saved',
        completed_steps: [],
        old_version_label: finishedCycle?.version_label || null,
        new_version_label: null,
        proposal_id: null,
        outcome: null,
        message: null,
        started_at: new Date().toISOString(),
        finished_at: null,
        error: null,
      }
      setLearningStatus(initialLearningStatus)
      setLearningTargetStatus(initialLearningStatus)
      setVisualLearningStatus(initialLearningStatus)
      setLearningStatusError('')
      setLearningWidgetOpen(true)
      setCurrentCycle(null)
      triggerLearningPipeline(finishedCycle?.id)
      void loadLearningStatus(finishedCycle?.id)
      await loadCurrentCycle()
      pushThought('Цикл выращивания завершён. Итоговый опросник сохранён.')
    } catch (error) {
      console.error('Failed to finish growing cycle', error)
      setFinishCycleError(getErrorMessage(error, 'Не удалось завершить цикл. Проверьте данные опросника и активный цикл.'))
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
    const canStartCycle = !isCycleLoading && !cropsLoading && !cropsError && Boolean(selectedCropSlug) && Boolean(selectedCrop) && !isSelectedCropLearningBlocked

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
              {cropsLoading ? (
                <div className="rounded-[20px] border border-white/10 bg-white/[0.035] px-4 py-5 text-sm text-white/68">
                  Загрузка культур...
                </div>
              ) : cropsError ? (
                <div className="rounded-[20px] border border-amber-300/20 bg-amber-300/10 px-4 py-4 text-sm text-amber-100">
                  <div>{cropsError}</div>
                  <button
                    type="button"
                    onClick={() => {
                      setCycleError('')
                      void loadCrops()
                    }}
                    className="mt-3 rounded-[14px] border border-amber-200/25 bg-amber-200/12 px-4 py-2 font-semibold text-amber-50 transition hover:bg-amber-200/18"
                  >
                    Повторить загрузку
                  </button>
                </div>
              ) : crops.length === 0 ? (
                <div className="rounded-[20px] border border-white/10 bg-white/[0.035] px-4 py-5 text-sm text-white/68">
                  В базе пока нет доступных культур
                </div>
              ) : (
                <div className="custom-scrollbar max-h-[260px] overflow-y-auto overflow-x-hidden pr-2 sm:max-h-[300px] min-[1700px]:max-h-[300px]">
                  <div className="grid grid-cols-2 gap-3 max-[360px]:grid-cols-1">
                    {crops.map(renderCropCard)}
                  </div>
                </div>
              )}
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
                  <p className="mt-2 text-sm text-white/58">Статус: активный цикл</p>
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

          <div className="relative min-w-0 max-w-full overflow-visible rounded-[26px] border border-white/8 bg-white/[0.035] p-4 sm:p-5">
            <div className="flex min-h-[260px] flex-col min-[1700px]:h-full min-[1700px]:min-h-0">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-lg font-semibold text-white">{isActive ? 'Параметры цикла' : 'Предпросмотр цикла'}</div>
                  <p className="mt-1 text-sm text-white/58">
                    {isActive ? 'Цикл выполняется по активной агротехкарте.' : 'Проверьте параметры и подтвердите запуск.'}
                  </p>
                </div>
                <LearningWidget
                  isOpen={learningWidgetOpen}
                  learningStatus={lastFinishedCycle ? visualLearningStatus : null}
                  learningResult={learningResult}
                  learningResultError={learningResultError}
                  loadError={learningStatusError}
                  onToggle={() => setLearningWidgetOpen((prev) => !prev)}
                  onClose={() => setLearningWidgetOpen(false)}
                  onExpand={() => {
                    if (!canOpenLearningDetails) return
                    setLearningModalOpen(true)
                  }}
                />
              </div>

              <div className="mt-5 grid min-w-0 flex-1 items-center gap-5 md:grid-cols-[112px_minmax(0,1fr)]">
                <div className={`mx-auto flex aspect-square w-[112px] items-center justify-center overflow-hidden rounded-[28px] border border-emerald-300/18 bg-gradient-to-br ${previewVisual.gradient} shadow-[0_0_34px_rgba(52,211,153,0.10)]`}>
                  {previewVisual.image ? (
                    <img
                      src={previewVisual.image}
                      alt=""
                      aria-hidden="true"
                      className="h-[92px] w-[92px] object-contain drop-shadow-[0_0_28px_rgba(52,211,153,0.22)]"
                      loading="lazy"
                      draggable="false"
                    />
                  ) : (
                    <span className="text-[58px] leading-none">
                      {previewVisual.emoji || '?'}
                    </span>
                  )}
                </div>

                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="min-w-0 max-w-full truncate text-[24px] font-semibold leading-tight text-white md:text-[28px]">{activeCropName}</div>
                    {isActive ? (
                      <span className="rounded-full border border-emerald-300/25 bg-emerald-300/10 px-3 py-1 text-sm text-emerald-200">
                        активный цикл
                      </span>
                    ) : null}
                  </div>

                  <div className="mt-5 divide-y divide-white/8">
                    {[
                      ['Агротехкарта', activeVersion],
                      ['День цикла', currentCycle?.day_number || 1],
                      ['Лоток', formatTrayName(currentCycle?.tray_id || DEFAULT_TRAY_ID)],
                    ].map(([label, value]) => (
                      <div key={label} className="flex items-center justify-between gap-4 py-3 text-sm">
                        <span className="text-white/54">{label}</span>
                        <span className="font-semibold text-white/88">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {!isActive && isSelectedCropLearningBlocked ? (
                <div className="mt-3 rounded-[18px] border border-amber-300/20 bg-amber-300/10 px-4 py-3 text-sm leading-snug text-amber-100">
                  Для этой культуры ещё обновляется АгроТехКарта после предыдущего цикла.
                </div>
              ) : null}

              <div className="mt-4 grid min-w-0 gap-3 md:grid-cols-[minmax(0,1fr)_140px]">
                {!isActive ? (
                  <>
                    <button
                      type="button"
                      onClick={handleStartCycle}
                      disabled={!canStartCycle}
                      className="inline-flex min-h-[56px] items-center justify-center gap-3 rounded-[20px] border border-violet-200/30 bg-gradient-to-r from-violet-500 to-fuchsia-600 px-5 py-3 font-semibold text-white shadow-[0_0_28px_rgba(168,85,247,0.28)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-55"
                    >
                      <PlayIcon className="h-4 w-4" />
                      {isCycleLoading ? 'Запуск...' : 'Подтвердить запуск'}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setCycleError('')
                        setSelectedCropSlug(crops[0]?.slug || '')
                      }}
                      disabled={crops.length === 0}
                      className="min-h-[56px] rounded-[20px] border border-white/10 bg-white/[0.035] px-5 py-3 font-semibold text-white/72 transition hover:bg-white/[0.065]"
                    >
                      Отмена
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={handleOpenFinishCycleModal}
                    disabled={isCycleLoading}
                    className="min-h-[56px] rounded-[20px] border border-rose-200/20 bg-rose-500/16 px-5 py-3 font-semibold text-rose-100 transition hover:bg-rose-500/22 disabled:cursor-not-allowed disabled:opacity-55 sm:col-span-2"
                  >
                    Закончить цикл
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

        <div className="min-h-[320px] max-h-[420px] min-w-0 overflow-hidden min-[1700px]:h-full min-[1700px]:min-h-0 min-[1700px]:max-h-none">
          <ThoughtStream thoughts={thoughts} className="h-full" />
        </div>
      </div>
    </div>
  )

  const renderPhTargetSettings = () => {
    const isDisabled = !currentCycle || phTargetLoading || phTargetSaving
    const rangeMin = phTargetRange ? formatPhRangeValue(phTargetRange.min) : null
    const rangeMax = phTargetRange ? formatPhRangeValue(phTargetRange.max) : null
    const canSave = Boolean(currentCycle) && isPhTargetValid && !phTargetLoading && !phTargetSaving
    const subtitle = currentCycle
      ? 'Система будет поддерживать это значение в текущем цикле'
      : 'Запустите цикл, чтобы задать целевой pH'
    const controlStatus = !currentCycle
      ? { text: 'pH-контроль: недоступен', className: 'border-white/8 bg-white/[0.035] text-white/42' }
      : phTargetConfigured
        ? { text: 'pH-контроль: активен', className: 'border-emerald-300/14 bg-emerald-300/[0.07] text-emerald-300' }
        : isPhTargetValid
          ? { text: 'pH-контроль: активен после сохранения', className: 'border-violet-300/16 bg-violet-300/[0.07] text-violet-200' }
          : { text: 'pH-контроль: не настроен', className: 'border-white/8 bg-white/[0.04] text-white/52' }

    return (
      <GlassCard
        padded={false}
        className={`rounded-[22px] ${
          currentCycle
            ? 'border-violet-400/14 bg-violet-500/[0.014] shadow-[0_0_18px_rgba(168,85,247,0.06)]'
            : 'border-white/8 bg-white/[0.015] opacity-80 shadow-none'
        }`}
      >
        <div className="grid min-w-0 items-end gap-3 p-3 md:grid-cols-2 xl:grid-cols-[210px_150px_140px_150px_230px_auto]">
          <div className="min-w-0 pb-1">
            <div className="text-[17px] font-semibold tracking-tight text-white">Целевой pH раствора</div>
            <p className="mt-0.5 truncate text-[12px] text-white/48">{subtitle}</p>
          </div>

          <label className="min-w-0">
            <span className="text-[11px] font-semibold text-white/64">Целевой pH</span>
            <div className="mt-1 flex h-10 items-center rounded-[12px] border border-white/10 bg-white/[0.04] px-3 focus-within:border-violet-300/35">
              <input
                type="number"
                min="3.5"
                max="9"
                step="0.1"
                inputMode="decimal"
                value={phTargetForm.targetPh}
                onChange={handlePhTargetFieldChange('targetPh')}
                disabled={isDisabled}
                placeholder={currentCycle ? '5.9' : ''}
                className="min-w-0 flex-1 bg-transparent text-[15px] font-semibold text-white outline-none placeholder:text-white/24 disabled:cursor-not-allowed"
              />
              <span className="ml-2 shrink-0 text-xs text-white/38">pH</span>
            </div>
          </label>

          <label className="min-w-0">
            <span className="text-[11px] font-semibold text-white/64">Допуск ±</span>
            <div className="mt-1 flex h-10 items-center rounded-[12px] border border-white/10 bg-white/[0.04] px-3 focus-within:border-violet-300/35">
              <input
                type="number"
                min="0.1"
                max="0.5"
                step="0.1"
                inputMode="decimal"
                value={phTargetForm.tolerance}
                onChange={handlePhTargetFieldChange('tolerance')}
                disabled={isDisabled}
                placeholder={currentCycle ? '0.1' : ''}
                className="min-w-0 flex-1 bg-transparent text-[15px] font-semibold text-white outline-none placeholder:text-white/24 disabled:cursor-not-allowed"
              />
              <span className="ml-2 shrink-0 text-xs text-white/38">pH</span>
            </div>
          </label>

          <div className="flex h-10 min-w-0 items-center gap-2 rounded-[12px] border border-cyan-300/10 bg-cyan-300/[0.04] px-3">
            <DropletIcon className="h-4 w-4 shrink-0 text-sky-300" />
            <div className="min-w-0 text-[12px] leading-tight">
              <span className="text-white/45">Диапазон: </span>
              <span className="font-semibold text-emerald-300">
                {rangeMin !== null && rangeMax !== null ? `${rangeMin}–${rangeMax}` : '—'}
              </span>
            </div>
          </div>

          <div className={`flex h-10 min-w-0 items-center rounded-[12px] border px-3 text-[12px] font-semibold leading-tight ${controlStatus.className}`}>
            <span className="truncate">{controlStatus.text}</span>
          </div>

          <button
            type="button"
            onClick={handleSavePhTarget}
            disabled={!canSave}
            className="h-10 whitespace-nowrap rounded-[12px] border border-violet-200/30 bg-gradient-to-r from-violet-500 to-fuchsia-600 px-4 text-[13px] font-semibold text-white shadow-[0_0_20px_rgba(168,85,247,0.22)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:border-white/8 disabled:bg-none disabled:bg-white/[0.04] disabled:text-white/36 disabled:shadow-none md:col-span-2 xl:col-span-1"
          >
            {phTargetSaving ? 'Сохранение...' : 'Сохранить'}
          </button>

          {phTargetMessage || phTargetError ? (
            <div className="text-[11px] leading-tight md:col-span-2 xl:col-span-6">
              {phTargetMessage ? <span className="font-semibold text-emerald-300">{phTargetMessage}</span> : null}
              {phTargetError ? <span className="font-semibold text-rose-300">{phTargetError}</span> : null}
            </div>
          ) : null}
        </div>
      </GlassCard>
    )
  }

  const renderManual = () => (
    <div className="custom-scrollbar flex min-w-0 max-w-full flex-col gap-3 min-[1700px]:h-full min-[1700px]:min-h-0 min-[1700px]:overflow-y-auto min-[1700px]:pr-1">
      <GlassCard className="shrink-0 rounded-[28px]">
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

      <div className="shrink-0">
        {renderPhTargetSettings()}
      </div>

      <div className="min-h-[300px] shrink-0">

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
  </div>
)

  const devDemoPanel = DEV_FEATURES_ENABLED ? (
    <div className="flex w-full max-w-[340px] shrink-0 items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.035] px-2 py-1 shadow-[0_12px_36px_rgba(0,0,0,0.12)] backdrop-blur-xl">
      <span className="rounded-lg border border-emerald-300/14 bg-emerald-300/[0.07] px-2 py-1 text-[11px] font-semibold text-emerald-200">
        DEV
      </span>
      <select
        value={selectedDemoCropSlug}
        onChange={(event) => {
          setSelectedDemoCropSlug(event.target.value)
          setDemoLearningError('')
        }}
        className="h-8 w-[124px] rounded-xl border border-white/10 bg-white/[0.04] px-2 text-xs font-medium text-white/82 outline-none transition hover:bg-white/[0.07] focus:border-emerald-300/40 focus:bg-slate-900/70"
      >
        {demoCropOptions.map((crop) => (
          <option key={crop.slug} value={crop.slug} className="bg-slate-950 text-white">
            {crop.name_ru || crop.slug}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={handleCreateDemoLearningResult}
        disabled={demoLearningLoading}
        className="h-8 w-[68px] rounded-xl border border-violet-200/20 bg-gradient-to-r from-violet-500/70 to-emerald-400/55 px-2 text-xs font-semibold text-white shadow-[0_0_18px_rgba(139,92,246,0.18)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {demoLearningLoading ? '...' : 'DEMO'}
      </button>
      {demoLearningError ? (
        <span className="max-w-[58px] truncate text-[11px] font-medium text-rose-200/90" title={demoLearningError}>
          {demoLearningError}
        </span>
      ) : null}
    </div>
  ) : null

  const renderActiveView = () => {
    if (mode === 'graphs') {
      return (
        <PhGraphsView
          data={phGraphData}
          loading={phGraphLoading}
          error={phGraphError}
          graphCycleId={graphCycleId}
          onLiveClick={() => {
            setGraphCycleId(null)
            void loadPhGraphData({ cycleId: null })
          }}
          onReload={() => void loadPhGraphData({ cycleId: graphCycleId })}
        />
      )
    }

    return mode === 'monitoring' ? renderMonitoring() : renderManual()
  }

  return (
    <div className="farm-shell relative min-h-screen overflow-x-hidden px-3 py-3 md:px-4 md:py-4 lg:px-6 lg:py-6 min-[1700px]:h-screen min-[1700px]:overflow-hidden">
      <div className="mx-auto flex w-full max-w-[1800px] flex-col gap-4 min-[1700px]:h-full">
        <HeaderBar
          mode={mode}
          setMode={setMode}
          currentTime={currentTime}
          currentDate={currentDate}
        />

        {devDemoPanel ? (
          <div className="flex min-w-0 justify-end">
            {devDemoPanel}
          </div>
        ) : null}

        <main className="grid min-w-0 gap-4 min-[1700px]:min-h-0 min-[1700px]:flex-1 min-[1700px]:grid-cols-[minmax(0,1fr)_340px] min-[1900px]:grid-cols-[minmax(0,1fr)_360px]">
          <div className="flex min-w-0 flex-col min-[1700px]:h-full min-[1700px]:min-h-0">{renderActiveView()}</div>

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
      {isFinishCycleModalOpen ? (
        <FinishCycleModal
          currentCycle={currentCycle}
          form={finishCycleForm}
          setForm={setFinishCycleForm}
          error={finishCycleError}
          isLoading={isCycleLoading}
          onClose={handleCloseFinishCycleModal}
          onSubmit={handleSubmitFinishCycle}
        />
      ) : null}
      {learningModalOpen ? (
        <LearningResultModal
          learningResult={learningResult}
          onClose={() => setLearningModalOpen(false)}
        />
      ) : null}
    </div>
  )
}
