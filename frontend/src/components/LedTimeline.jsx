import GlassCard from './GlassCard'
import { MoonIcon, PlayIcon, SunIcon } from './Icons'

export default function LedTimeline({
  stages,
  activeIndex,
  isPlaying,
  isStarting = false,
  progress = 0,
  statusText,
  onPlay,
  compact = false,
}) {
  const normalizedProgress = Math.min(100, Math.max(0, progress * 100))
  const playButton = (
    <button
      type="button"
      onClick={onPlay}
      disabled={isStarting}
      className="group flex w-full shrink-0 items-center justify-center gap-3 whitespace-nowrap rounded-[20px] border border-violet-200/18 bg-gradient-to-r from-violet-500/75 to-fuchsia-500/65 px-4 py-3 text-sm font-medium text-white transition hover:scale-[1.01] hover:brightness-110 disabled:cursor-wait disabled:opacity-70 md:px-7 lg:w-[270px]"
      style={{ boxShadow: '0 18px 36px rgba(173, 78, 255, 0.24)' }}
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/14">
        <PlayIcon className="h-4 w-4" />
      </span>
      {isStarting ? 'Отправляю команду…' : isPlaying ? 'Световой день идёт' : 'Запустить световой день'}
    </button>
  )

  return (
    <GlassCard className="flex h-full min-h-[260px] flex-col rounded-[28px]">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="text-[22px] font-semibold tracking-tight md:text-[24px]">
            Управление LED лентой
          </div>

          <p className="mt-1.5 text-sm text-white/64">
            {statusText ? `Стадия: ${statusText}` : 'Стадия: ожидание'}
          </p>
        </div>

        {compact ? (
          <div className="shrink-0 lg:pt-1">
            {playButton}
          </div>
        ) : (
          <div className="hidden rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-white/55 lg:block">
            06:00 — 22:00
          </div>
        )}
      </div>

      <div className="mt-4 min-h-[116px] shrink-0">
        <div className="relative grid grid-cols-5 gap-3 md:grid-cols-10">
          <div className="absolute left-2 right-2 top-[28px] h-[2px] bg-gradient-to-r from-cyan-300 via-yellow-300 to-fuchsia-400 opacity-80 md:top-[31px]" />

          {stages.map((stage, index) => {
            const active = isPlaying ? index <= activeIndex : true
            const current = index === activeIndex

            return (
              <div key={stage.id} className="relative z-10 flex flex-col items-center gap-2 text-center">
                <div
                  className={`flex h-14 w-14 items-center justify-center rounded-full border transition-all duration-300 md:h-[62px] md:w-[62px] ${
                    current ? 'scale-105 border-white/55' : 'border-white/18'
                  }`}
                  style={{
                    background: active
                      ? `radial-gradient(circle at 30% 28%, rgba(255,255,255,0.68), ${stage.color})`
                      : 'radial-gradient(circle at 30% 28%, rgba(255,255,255,0.16), rgba(255,255,255,0.08))',
                    color: active ? '#fff' : 'rgba(255,255,255,0.72)',
                    boxShadow: active
                      ? `0 0 28px ${stage.color}95, 0 0 52px ${stage.color}30, inset 0 1px 0 rgba(255,255,255,0.42)`
                      : 'inset 0 1px 0 rgba(255,255,255,0.08)',
                  }}
                >
                  {stage.moon ? <MoonIcon className="h-6 w-6" /> : <SunIcon className="h-6 w-6" />}
                </div>

                <div className={`text-xs font-semibold md:text-sm ${current ? 'text-white' : 'text-white/88'}`}>
                  {stage.id}
                </div>

                {!compact && <div className="hidden text-[11px] text-white/58 md:block">{stage.label}</div>}

                <div className="text-[11px] text-white/48 md:text-xs">{stage.time}</div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="mt-4 h-[5px] overflow-hidden rounded-full bg-white/8">
        <div
          className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-yellow-300 to-fuchsia-400 transition-[width] duration-150"
          style={{ width: `${normalizedProgress}%` }}
        />
      </div>

      {!compact && (
        <div className="mt-5 flex w-full justify-end lg:justify-center 2xl:justify-end">
          {playButton}
        </div>
      )}
    </GlassCard>
  )
}
