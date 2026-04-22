import GlassCard from './GlassCard'
import Toggle from './Toggle'

export default function DeviceCard({
  icon,
  title,
  subtitle,
  level,
  enabled,
  onToggle,
  accent,
  action,
}) {
  return (
    <GlassCard soft className="rounded-[24px] px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[18px] border border-white/10"
            style={{ backgroundColor: `${accent}20`, color: accent, boxShadow: `inset 0 1px 0 rgba(255,255,255,0.12), 0 0 22px ${accent}18` }}
          >
            {icon}
          </div>
          <div className="min-w-0">
            <h3 className="text-[18px] font-semibold leading-6 tracking-tight text-white">{title}</h3>
            <p className="mt-1 text-sm leading-5 text-white/68">
              {subtitle}: {level}%
            </p>
          </div>
        </div>
        {action ?? <Toggle checked={enabled} onChange={onToggle} />}
      </div>
      <div className="mt-4 h-[5px] rounded-full bg-white/8">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{
            width: `${level}%`,
            background: `linear-gradient(90deg, ${accent}, rgba(255,255,255,0.78))`,
            boxShadow: `0 0 16px ${accent}55`,
          }}
        />
      </div>
    </GlassCard>
  )
}
