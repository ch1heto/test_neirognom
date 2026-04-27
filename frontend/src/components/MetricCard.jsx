import GlassCard from './GlassCard'

function createSmoothPath(values) {
  const safeValues = Array.isArray(values) && values.length > 1 ? values : [0, 0]
  const max = Math.max(...safeValues)
  const min = Math.min(...safeValues)
  const range = max - min

  const getPoint = (value, index) => {
    const x = (index / (safeValues.length - 1)) * 400
    const normalized = range > 0 ? (value - min) / range : 0.5
    const y = 78 - normalized * 52
    return { x, y }
  }

  const points = safeValues.map(getPoint)
  let path = `M ${points[0].x} ${points[0].y}`

  for (let index = 0; index < points.length - 1; index += 1) {
    const current = points[index]
    const next = points[index + 1]
    const controlX = (current.x + next.x) / 2
    path += ` C ${controlX} ${current.y}, ${controlX} ${next.y}, ${next.x} ${next.y}`
  }

  return { path, points }
}

function Sparkline({ values, color, title, muted = false, compact = false }) {
  const { path, points } = createSmoothPath(values)
  const lastPoint = points.at(-1)
  const gradientId = `fill-${title.replace(/\s+/g, '-').toLowerCase()}`
  const glowId = `glow-${title.replace(/\s+/g, '-').toLowerCase()}`

  return (
    <svg
      viewBox="0 0 400 100"
      className={`h-[44px] w-full overflow-visible ${muted ? 'opacity-55' : ''}`}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.38" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
        <filter id={glowId} x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {[22, 50, 78].map((value) => (
        <line
          key={value}
          x1="0"
          x2="400"
          y1={value}
          y2={value}
          stroke="rgba(255,255,255,0.08)"
          strokeDasharray="3 4"
          strokeWidth="0.8"
        />
      ))}

      <path d={`${path} L 400 100 L 0 100 Z`} fill={`url(#${gradientId})`} />
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        filter={`url(#${glowId})`}
      />
      <circle cx={lastPoint.x} cy={lastPoint.y} r="2.6" fill={color} filter={`url(#${glowId})`} />
    </svg>
  )
}

export default function MetricCard({
  icon,
  title,
  value,
  unit,
  norm,
  color,
  values,
}) {
  const hasValue = value !== null && value !== undefined

  return (
    <GlassCard soft className="h-[152px] overflow-hidden rounded-[24px] px-4 py-3">
      <div className="flex h-full min-w-0 flex-col justify-between gap-2">
        <div className="flex min-w-0 items-center gap-3">
          <div
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[18px] border border-white/10"
            style={{
              backgroundColor: `${color}15`,
              color,
              boxShadow: `inset 0 1px 0 rgba(255,255,255,0.1), 0 8px 20px ${color}15`,
            }}
          >
            {icon}
          </div>

          <div className="min-w-0">
            <div className="text-[12px] font-medium uppercase tracking-wider text-white/40">
              {title}
            </div>

            <div className="mt-1 flex min-w-0 items-baseline gap-1.5">
              <span className={`${hasValue ? 'text-[30px]' : 'text-[16px]'} truncate font-bold leading-none tracking-tight text-white`}>
                {hasValue ? value : 'нет данных'}
              </span>

              {hasValue && unit ? (
                <span className="text-[14px] text-white/50">
                  {unit}
                </span>
              ) : null}
            </div>

            <div className="mt-1 text-[12px] font-medium" style={{ color: `${color}cc` }}>
              {norm}
            </div>
          </div>
        </div>

        <div className="min-w-0">
          <Sparkline values={values} color={color} title={title} muted={!hasValue} />
        </div>
      </div>
    </GlassCard>
  )
}
