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
            ['Лоток', currentCycle?.tray_id || DEFAULT_TRAY_ID],
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
  const [isFinishCycleModalOpen, setIsFinishCycleModalOpen] = useState(false)
  const [finishCycleForm, setFinishCycleForm] = useState(createInitialFinishCycleForm)
  const [finishCycleError, setFinishCycleError] = useState('')

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
      await requestJson('/api/cycles/end', {
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
      setCurrentCycle(null)
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
    </div>
  )
}
