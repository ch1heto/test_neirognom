import { useEffect, useMemo, useState } from 'react'
import GlassCard from './GlassCard'
import gnomeAvatar from '../assets/gnome.gif'
import { SendIcon } from './Icons'

function Bubble({ message }) {
  const isAssistant = message.from === 'assistant'
  return (
    <div className={`flex ${isAssistant ? 'justify-start' : 'justify-end'}`}>
      <div
        className={`max-w-[92%] rounded-[22px] px-4 py-2.5 text-sm leading-6 ${
          isAssistant
            ? 'border border-white/12 bg-white/[0.07] text-white/88 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
            : 'border border-emerald-200/12 bg-emerald-400/14 text-white'
        }`}
      >
        <div className="relative min-h-[24px] pr-14">
          <div className="text-sm leading-6 text-white">
            {message.text}
          </div>

          <div className="absolute bottom-0 right-0 text-[11px] text-white/42">
            {message.time}
          </div>
        </div>
      </div>
    </div>
  )
}

function ThinkingStatus({ steps = [] }) {
  const safeSteps = useMemo(
    () => (steps.length > 0 ? steps : ['Нейрогном думает']),
    [steps],
  )

  const [stepIndex, setStepIndex] = useState(0)
  const [dotCount, setDotCount] = useState(1)

  useEffect(() => {
    setStepIndex(0)
    setDotCount(1)
  }, [safeSteps])

  useEffect(() => {
    const dotTimer = setInterval(() => {
      setDotCount((prev) => (prev >= 3 ? 1 : prev + 1))
    }, 420)

    const stepTimer = setInterval(() => {
      setStepIndex((prev) => (prev + 1) % safeSteps.length)
    }, 1700)

    return () => {
      clearInterval(dotTimer)
      clearInterval(stepTimer)
    }
  }, [safeSteps])

  return (
    <div className="flex justify-start pl-1">
      <div className="inline-flex max-w-[92%] items-center gap-2 rounded-full border border-white/10 bg-white/[0.035] px-3 py-1.5 text-xs text-white/48">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-300/70" />
        <span>
          {safeSteps[stepIndex]}
          {'.'.repeat(dotCount)}
        </span>
      </div>
    </div>
  )
}

export default function ChatPanel({
  messages,
  input,
  onInput,
  onSend,
  isThinking = false,
  thinkingSteps = [],
  className = "",
}) {
  return (
    <GlassCard className={`flex h-full min-h-0 flex-col rounded-[28px] ${className}`}>
      <div className="flex items-center gap-3 shrink-0">
        <div 
          className="relative h-14 w-14 shrink-0 overflow-hidden md:h-16 md:w-16 opacity-85 transition-opacity hover:opacity-100"
          style={{
            maskImage: 'radial-gradient(circle, black 30%, transparent 75%)',
            WebkitMaskImage: 'radial-gradient(circle, black 30%, transparent 75%)'
          }}
        >
          <img 
            src={gnomeAvatar} 
            alt="Нейрогном" 
            className="h-full w-full object-cover scale-[1.25] brightness-110 contrast-125" 
          />
          <div className="absolute inset-0 bg-violet-500/25 mix-blend-color pointer-events-none" />
        </div>
        <div className="min-w-0">
          <div className="text-[18px] font-semibold tracking-tight md:text-[20px]">Чат Нейрогнома</div>
          <div className="mt-1.5 inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" /> Онлайн
          </div>
        </div>
      </div>

      <div className="custom-scrollbar mt-2 flex-1 space-y-2 overflow-y-auto pr-1">
        {messages.map((message) => (
          <Bubble key={message.id} message={message} />
        ))}

        {isThinking && <ThinkingStatus steps={thinkingSteps} />}
      </div>

      <form
        className="mt-2 flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          onSend()
        }}
      >
        <div className="glass-panel-soft flex-1 rounded-[20px] px-4 py-3">
          <input
            value={input}
            onChange={(event) => onInput(event.target.value)}
            disabled={isThinking}
            placeholder={isThinking ? 'Нейрогном формирует ответ…' : 'Напишите сообщение…'}
            className="w-full bg-transparent text-sm text-white placeholder:text-white/35 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
          />
        </div>
        <button
          type="submit"
          disabled={isThinking}
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[18px] border border-violet-200/18 bg-gradient-to-br from-violet-500/75 to-fuchsia-500/70 text-white transition hover:scale-[1.03] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
          style={{ boxShadow: '0 12px 26px rgba(173, 78, 255, 0.25)' }}
        >
          <SendIcon className="h-5 w-5" />
        </button>
      </form>
    </GlassCard>
  )
}
