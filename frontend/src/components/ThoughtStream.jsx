import GlassCard from './GlassCard'
import { BrainIcon } from './Icons'

export default function ThoughtStream({ thoughts, className = '' }) {
  return (
    <GlassCard className={`flex h-full min-h-0 min-w-0 max-w-full flex-col overflow-hidden rounded-[28px] ${className}`}>
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-[18px] border border-white/10 bg-violet-400/14 text-violet-200">
          <BrainIcon className="h-5 w-5" />
        </div>
        <div>
          <div className="text-[22px] font-semibold tracking-tight">Мысли сети</div>
          <p className="mt-1 text-sm text-white/60">Лог решений системы.</p>
        </div>
      </div>

      <div 
        className="custom-scrollbar mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto overflow-x-hidden pr-2"
        style={{
          maskImage: 'linear-gradient(to bottom, transparent, black 10%, black 90%, transparent)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent, black 10%, black 90%, transparent)'
        }}
      >
        <div className="h-4" /> 
        
        {thoughts.map((thought) => (
          <div 
            key={thought.id} 
            className="glass-panel-soft rounded-[22px] px-4 py-3 animate-in fade-in slide-in-from-right-2 duration-500"
          >
            <div className="text-sm leading-6 text-white/88">{thought.text}</div>
            <div className="mt-2 text-[11px] text-white/42">{thought.time}</div>
          </div>
        ))}

        <div className="h-4" />
      </div>
    </GlassCard>
  )
}
