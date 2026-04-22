import GlassCard from './GlassCard'
import { LeafIcon } from './Icons'

const items = [
  { label: 'Ферма работает', value: 'без сбоев' },
  { label: 'Последнее обновление', value: 'идёт в реальном времени' },
  { label: 'Онлайн', value: 'контроллер и датчики' },
]

export default function SystemFooter() {
  return (
    <GlassCard className="rounded-[30px]">
      <div className="grid gap-4 md:grid-cols-[0.9fr_1fr_1fr]">
        <div className="flex items-center gap-4 rounded-[24px] border border-white/10 bg-white/[0.03] px-4 py-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/8 text-white/90">
            <LeafIcon className="h-6 w-6" />
          </div>
          <div>
            <div className="text-sm text-white/56">{items[0].label}</div>
            <div className="mt-1 text-lg font-medium text-white">{items[0].value}</div>
          </div>
        </div>

        {items.slice(1).map((item) => (
          <div key={item.label} className="rounded-[24px] border border-white/10 bg-white/[0.03] px-4 py-4">
            <div className="text-sm text-white/56">{item.label}</div>
            <div className="mt-2 text-lg font-medium text-white">{item.value}</div>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}
