export default function ModeSwitch({ mode, onChange }) {
  const items = [
    { id: 'monitoring', label: 'Мониторинг' },
    { id: 'graphs', label: 'Графики' },
    { id: 'manual', label: 'Ручное управление' },
  ]

  return (
    <div className="glass-panel-soft inline-flex rounded-2xl p-1.5">
      {items.map((item) => {
        const active = item.id === mode
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onChange(item.id)}
            className={`rounded-xl px-3 py-2 text-sm font-medium transition-all duration-200 md:px-4 ${
              active
                ? 'bg-white/12 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.14)]'
                : 'text-white/65 hover:text-white'
            }`}
          >
            {item.label}
          </button>
        )
      })}
    </div>
  )
}
