import GlassCard from './GlassCard'

function createSmoothPath(values) {
  const max = Math.max(...values)
  const min = Math.min(...values)
  const getPoint = (value, index) => {
    const x = (index / (values.length - 1)) * 400
    const y = 100 - ((value - min) / Math.max(max - min, 1)) * 56 - 20
    return { x, y }
  }

  const points = values.map(getPoint)
  let path = `M ${points[0].x} ${points[0].y}`

  for (let index = 0; index < points.length - 1; index += 1) {
    const current = points[index]
    const next = points[index + 1]
    const controlX = (current.x + next.x) / 2
    path += ` C ${controlX} ${current.y}, ${controlX} ${next.y}, ${next.x} ${next.y}`
  }

  return { path, points }
}

function Sparkline({ values, color, title }) {
  const { path, points } = createSmoothPath(values)
  const lastPoint = points.at(-1)
  const gradientId = `fill-${title.replace(/\s+/g, '-').toLowerCase()}`
  const glowId = `glow-${title.replace(/\s+/g, '-').toLowerCase()}`

  return (
    <svg viewBox="0 0 400 100" className="h-28 w-full overflow-visible" preserveAspectRatio="none">
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
  return (
    <GlassCard soft className="overflow-hidden rounded-[28px] px-6 py-5">
      <div className="flex flex-col gap-6 md:flex-row md:items-center">
        <div className="flex shrink-0 items-center gap-5 md:w-64">
          <div
            className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-white/10"
            style={{
              backgroundColor: `${color}15`,
              color,
              boxShadow: `inset 0 1px 0 rgba(255,255,255,0.1), 0 8px 20px ${color}15`,
            }}
          >
            {icon}
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium uppercase tracking-wider text-white/40">{title}</div>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className="text-4xl font-bold tracking-tight text-white">{value}</span>
              <span className="text-lg text-white/50">{unit}</span>
            </div>
            <div className="mt-1 text-[13px] font-medium" style={{ color: `${color}cc` }}>
              {norm}
            </div>
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <Sparkline values={values} color={color} title={title} />
        </div>
      </div>
    </GlassCard>
  )
}
