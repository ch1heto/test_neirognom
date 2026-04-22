export default function GlassCard({
  children,
  className = '',
  padded = true,
  soft = false,
}) {
  return (
    <section
      className={`${soft ? 'glass-panel-soft' : 'glass-panel'} rounded-[28px] ${
        padded ? 'p-4 md:p-5' : ''
      } ${className}`}
    >
      {children}
    </section>
  )
}
