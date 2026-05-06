import { BellIcon, LeafIcon } from './Icons'
import ModeSwitch from './ModeSwitch'

export default function HeaderBar({ mode, setMode, currentTime, currentDate }) {
  return (
    <header className="grid gap-4 xl:grid-cols-[1.18fr_0.82fr_0.5fr]">
      <div className="glass-panel relative overflow-hidden rounded-[28px] px-5 py-4 md:px-6">
        <div className="absolute inset-y-0 left-0 w-28 bg-gradient-to-r from-emerald-400/15 to-transparent" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/15 bg-emerald-400/14 text-emerald-300">
              <LeafIcon className="h-6 w-6" />
            </div>
            <div>
              <div className="text-[24px] font-semibold leading-none tracking-tight gradient-text md:text-[28px]">
                Нейроагроном
              </div>
              <p className="mt-1.5 text-sm text-white/62">
                Умная сити-ферма
              </p>
            </div>
          </div>
          <ModeSwitch mode={mode} onChange={setMode} />
        </div>
      </div>

      <div className="glass-panel rounded-[28px] px-5 py-4">
        <div className="flex h-full items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 text-lg font-medium text-white">
              <span className="inline-block h-3 w-3 animate-pulseSoft rounded-full bg-emerald-400 shadow-[0_0_18px_rgba(52,211,153,0.7)]" />
              Ферма активна
            </div>
            <p className="mt-2 max-w-xs text-sm leading-6 text-white/70">
              Все системы работают в норме, LED-сценарий готов к запуску.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/50">
            LIVE
          </div>
        </div>
      </div>

      <div className="glass-panel rounded-[28px] px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[34px] font-semibold leading-none tracking-tight">{currentTime}</div>
            <div className="mt-2 text-sm text-white/60">{currentDate}</div>
          </div>
          <button
            type="button"
            className="glass-panel-soft flex h-11 w-11 items-center justify-center rounded-2xl text-white/80 transition hover:text-white"
          >
            <BellIcon className="h-5 w-5" />
          </button>
        </div>
      </div>
    </header>
  )
}
