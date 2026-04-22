import GlassCard from './GlassCard'
import { BrainIcon } from './Icons'

export default function ThoughtStream({ thoughts }) {
  return (
    <GlassCard className="flex h-full min-h-0 flex-col rounded-[28px]">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-[18px] border border-white/10 bg-violet-400/14 text-violet-200">
          <BrainIcon className="h-5 w-5" />
        </div>
        <div>
          <div className="text-[22px] font-semibold tracking-tight">Мысли сети</div>
          <p className="mt-1 text-sm text-white/60">Короткие заметки о том, что система решила сделать.</p>
        </div>
      </div>

      <div className="mt-4 grid flex-1 gap-3">
        {thoughts.slice(0, 3).map((thought) => (
          <div key={thought.id} className="glass-panel-soft rounded-[22px] px-4 py-3">
            <div className="text-sm leading-6 text-white/88">{thought.text}</div>
            <div className="mt-2 text-[11px] text-white/42">{thought.time}</div>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}
