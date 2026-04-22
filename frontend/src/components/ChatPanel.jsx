import GlassCard from './GlassCard'
import gnomeAvatar from '../assets/gnome.png'
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
      <div className="flex items-start gap-3">
        <div className="glass-panel-soft overflow-hidden rounded-[22px] p-2">
          <img 
            src={gnomeAvatar} 
            alt="Нейрогном" 
            className="h-16 w-16 rounded-[18px] object-cover md:h-20 md:w-20" 
          />
        </div>
        <div className="min-w-0 pt-1">
          <div className="text-[22px] font-semibold tracking-tight md:text-[24px]">Чат Нейрогнома</div>
          <div className="mt-2 inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300 md:text-sm">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /> Онлайн
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
