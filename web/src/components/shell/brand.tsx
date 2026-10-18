export function BrandMark({ className = "size-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" className={className} aria-hidden>
      <rect width="28" height="28" rx="7" fill="#172033" />
      <path
        d="M5 20.5h3.2l2.2-4.6 2.6 6.1 3.4-13.5 2.8 9.2 1.6-2.7H23"
        fill="none"
        stroke="#ffffff"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="16.4" cy="8.5" r="1.9" fill="#0f9d9a" />
    </svg>
  );
}
