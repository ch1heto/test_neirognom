const base = 'fill-none stroke-current'

export function LeafIcon({ className = 'h-6 w-6' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <path d="M5 17c4.2 0 7.7-1.4 10.4-4.1C18.2 10.2 19.7 6.7 20 3c-3.7.3-7.2 1.8-9.9 4.6C7.4 10.3 6 13.8 6 18" />
      <path d="M4 21c2.2-4.2 5.4-7.4 9.5-9.5" />
    </svg>
  )
}

export function DropletIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <path d="M12 3c3.2 4.1 6 7.1 6 10.2a6 6 0 0 1-12 0C6 10.1 8.8 7.1 12 3Z" />
      <path d="M9.7 15.6c.4.8 1.2 1.4 2.3 1.6" strokeLinecap="round" />
    </svg>
  )
}

export function ThermometerIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <path d="M14 14.8V5.5a2 2 0 1 0-4 0v9.3a4 4 0 1 0 4 0Z" />
      <path d="M12 11v5" strokeLinecap="round" />
    </svg>
  )
}

export function HumidityIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <path d="M12 3c3.6 4.4 6.8 7.6 6.8 11.2A6.8 6.8 0 1 1 5.2 14.2C5.2 10.6 8.4 7.4 12 3Z" />
      <path d="M9 11.5c.6-.9 1.2-1.7 3-3.7" strokeLinecap="round" />
    </svg>
  )
}

export function FanIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <circle cx="12" cy="12" r="1.8" />
      <path d="M12.7 5.1c1.8-1 4.5-.3 5.4 1.7.6 1.3.4 3.1-.7 4.4-1.4 1.6-3.5 1.7-5 1.3" />
      <path d="M18.8 13.3c2 .6 3.3 3.1 2.6 5.1-.5 1.3-1.9 2.5-3.5 2.8-2.1.4-3.8-.9-4.8-2.1" />
      <path d="M10.3 18.9c-.8 1.9-3.3 3-5.3 2.1-1.3-.6-2.4-2.1-2.6-3.7-.3-2.1 1.1-3.8 2.4-4.7" />
      <path d="M5 10.7c-1.9-.8-2.9-3.4-2-5.3C3.6 4.1 5.1 3 6.7 2.9c2.1-.2 3.8 1.2 4.7 2.5" />
    </svg>
  )
}

export function LightIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <path d="M9.2 18h5.6" strokeLinecap="round" />
      <path d="M9.7 21h4.6" strokeLinecap="round" />
      <path d="M8 14.2c0-1-.5-1.8-1.1-2.7A6.3 6.3 0 1 1 17 11.5c-.6.9-1 1.7-1 2.7V15H8v-.8Z" />
      <path d="M12 2.5v1.7" strokeLinecap="round" />
      <path d="M4.6 5.6 5.8 6.8" strokeLinecap="round" />
      <path d="M19.4 5.6 18.2 6.8" strokeLinecap="round" />
    </svg>
  )
}

export function PumpIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <path d="M5 10c1.2 0 1.8-.6 2.5-1.2.7-.7 1.3-1.3 2.5-1.3s1.8.6 2.5 1.3c.7.6 1.3 1.2 2.5 1.2s1.8-.6 2.5-1.2c.7-.7 1.3-1.3 2.5-1.3" strokeLinecap="round" />
      <path d="M3 15c1.2 0 1.8-.6 2.5-1.2.7-.7 1.3-1.3 2.5-1.3s1.8.6 2.5 1.3c.7.6 1.3 1.2 2.5 1.2s1.8-.6 2.5-1.2c.7-.7 1.3-1.3 2.5-1.3" strokeLinecap="round" />
      <path d="M7 5.5c1.6 0 2.8-1.2 2.8-2.8S8.6 0 7 0 4.2 1.2 4.2 2.8 5.4 5.5 7 5.5Z" transform="translate(5 2.5)"/>
    </svg>
  )
}

export function LedIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <path d="M12 6.5a4 4 0 0 1 4 4c0 1.3-.5 2.2-1.3 3-.8.8-1.2 1.5-1.2 2.5h-3c0-1-.4-1.7-1.2-2.5a4.1 4.1 0 0 1-1.3-3 4 4 0 0 1 4-4Z" />
      <path d="M10 18h4" strokeLinecap="round" />
      <path d="M9 21h6" strokeLinecap="round" />
      <path d="M12 2.5v1.5M4.9 5.4l1 1M19.1 5.4l-1 1M2.5 12H4M20 12h1.5" strokeLinecap="round" />
    </svg>
  )
}

export function BellIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <path d="M7 9a5 5 0 1 1 10 0c0 5.2 2 6 2 6H5s2-.8 2-6Z" />
      <path d="M10.5 18a1.5 1.5 0 0 0 3 0" strokeLinecap="round" />
    </svg>
  )
}

export function SendIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <path d="M4 11.5 19.5 4 15 20l-3.8-5.2L4 11.5Z" />
      <path d="M11.2 14.8 19.5 4" strokeLinecap="round" />
    </svg>
  )
}

export function BrainIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <path d="M9.5 6.5A3.5 3.5 0 1 1 16 8v8a3 3 0 1 1-3 3H11a3 3 0 1 1-3-3V8a3.5 3.5 0 0 1 1.5-1.5Z" />
      <path d="M9 9H7a2.5 2.5 0 1 1 0-5" strokeLinecap="round" />
      <path d="M15 9h2a2.5 2.5 0 1 0 0-5" strokeLinecap="round" />
      <path d="M9 14H7a2.5 2.5 0 1 0 0 5" strokeLinecap="round" />
      <path d="M15 14h2a2.5 2.5 0 1 1 0 5" strokeLinecap="round" />
    </svg>
  )
}

export function SunIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 2.4v2.2M12 19.4v2.2M4.6 4.6l1.5 1.5M17.9 17.9l1.5 1.5M2.4 12h2.2M19.4 12h2.2M4.6 19.4l1.5-1.5M17.9 6.1l1.5-1.5" strokeLinecap="round" />
    </svg>
  )
}

export function MoonIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <path d="M19 13.6A7.6 7.6 0 0 1 10.4 5a8.4 8.4 0 1 0 8.6 8.6Z" />
    </svg>
  )
}

export function PlayIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <path d="M8 6.5 17 12l-9 5.5V6.5Z" fill="currentColor" stroke="none" />
    </svg>
  )
}

export function SlidersIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 24 24" className={`${base} ${className}`} strokeWidth="1.8">
      <path d="M4 6h8M16 6h4M4 12h4M12 12h8M4 18h10M18 18h2" strokeLinecap="round" />
      <circle cx="14" cy="6" r="2" />
      <circle cx="8" cy="12" r="2" />
      <circle cx="16" cy="18" r="2" />
    </svg>
  )
}
