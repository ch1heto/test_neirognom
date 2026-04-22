export default function Toggle({ checked, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-11 w-[78px] shrink-0 items-center rounded-full border p-1 transition-all duration-300 ${
        checked
          ? 'border-emerald-300/28 bg-emerald-300/12 shadow-[0_0_32px_rgba(74,222,128,0.12)]'
          : 'border-white/12 bg-white/[0.06]'
      }`}
      aria-pressed={checked}
    >
      <span
        className={`absolute inset-[3px] rounded-full transition-all duration-300 ${
          checked
            ? 'bg-gradient-to-r from-emerald-300/18 via-cyan-300/10 to-transparent'
            : 'bg-white/[0.03]'
        }`}
      />
      <span
        className={`relative z-10 flex h-9 w-9 items-center justify-center rounded-full border transition-all duration-300 ${
          checked
            ? 'translate-x-[34px] border-white/65 bg-white shadow-[0_8px_24px_rgba(255,255,255,0.35)]'
            : 'translate-x-0 border-white/16 bg-white/85 shadow-[0_8px_20px_rgba(0,0,0,0.22)]'
        }`}
      >
        <span className={`h-2.5 w-2.5 rounded-full ${checked ? 'bg-emerald-500' : 'bg-slate-500'}`} />
      </span>
    </button>
  )
}
