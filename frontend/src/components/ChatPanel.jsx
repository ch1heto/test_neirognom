import GlassCard from './GlassCard'
import gnomeAvatar from '../assets/gnome.gif'
import { SendIcon } from './Icons'

function Bubble({ message }) {
  const isAssistant = message.from === 'assistant'
  return (
    <div className={`flex ${isAssistant ? 'justify-start' : 'justify-end'}`}>
      <div
        className={`max-w-[92%] rounded-[22px] px-4 py-3 text-sm leading-6 ${
          isAssistant
            ? 'border border-white/12 bg-white/[0.07] text-white/88 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
            : 'border border-emerald-200/12 bg-emerald-400/14 text-white'
        }`}
      >
        <div>{message.text}</div>
        <div className="mt-2 text-right text-[11px] text-white/42">{message.time}</div>
      </div>
    </div>
  )
}

export default function ChatPanel({ messages, input, onInput, onSend, className = "" }) {
  return (
    <GlassCard className={`flex h-full min-h-0 flex-col rounded-[28px] ${className}`}>
      <div className="flex items-center gap-5 shrink-0">
        <div 
          className="relative h-20 w-20 shrink-0 overflow-hidden md:h-24 md:w-24 opacity-85 transition-opacity hover:opacity-100"
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
          <div className="text-[22px] font-semibold tracking-tight md:text-[24px]">Чат ассистента</div>
          <div className="mt-1.5 inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" /> Онлайн
          </div>
        </div>
      </div>

      <div className="custom-scrollbar mt-4 flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.map((message) => (
          <Bubble key={message.id} message={message} />
        ))}
      </div>

      <form
        className="mt-4 flex items-center gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          onSend()
        }}
      >
        <div className="glass-panel-soft flex-1 rounded-[20px] px-4 py-3">
          <input
            value={input}
            onChange={(event) => onInput(event.target.value)}
            placeholder="Напишите сообщение…"
            className="w-full bg-transparent text-sm text-white placeholder:text-white/35 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[18px] border border-violet-200/18 bg-gradient-to-br from-violet-500/75 to-fuchsia-500/70 text-white transition hover:scale-[1.03]"
          style={{ boxShadow: '0 12px 26px rgba(173, 78, 255, 0.25)' }}
        >
          <SendIcon className="h-5 w-5" />
        </button>
      </form>
    </GlassCard>
  )
}
