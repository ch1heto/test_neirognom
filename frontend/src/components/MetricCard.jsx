import GlassCard from './GlassCard'

function createSmoothPath(values) {
  const max = Math.max(...values)
  const min = Math.min(...values)
  const getPoint = (value, index) => {
    const x = (index / (values.length - 1)) * 100
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
    <svg viewBox="0 0 100 100" className="h-24 w-full overflow-visible">
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
          x2="100"
          y1={value}
          y2={value}
          stroke="rgba(255,255,255,0.08)"
          strokeDasharray="3 4"
          strokeWidth="0.8"
        />
      ))}

      <path d={`${path} L 100 100 L 0 100 Z`} fill={`url(#${gradientId})`} />
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
    <GlassCard soft className="overflow-hidden rounded-[26px] px-5 py-4">
      <div className="flex items-start gap-4">
        <div
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[18px] border border-white/10"
          style={{
            backgroundColor: `${color}20`,
            color,
            boxShadow: `inset 0 1px 0 rgba(255,255,255,0.12), 0 0 24px ${color}18`,
          }}
        >
          {icon}
        </div>
        <div className="min-w-0">
          <div className="text-[17px] text-white/78">{title}</div>
          <div className="mt-2 flex items-end gap-2">
            <span className="text-[38px] font-semibold leading-none tracking-tight md:text-[40px]">{value}</span>
            <span className="pb-1 text-lg text-white/68">{unit}</span>
          </div>
        </div>
      </div>
      <div className="mt-2 rounded-[20px] bg-white/[0.02] px-1 py-2">
        <Sparkline values={values} color={color} title={title} />
      </div>
      <div className="mt-1 text-[15px] font-medium" style={{ color }}>
        Норма: {norm}
      </div>
    </GlassCard>
  )
}
