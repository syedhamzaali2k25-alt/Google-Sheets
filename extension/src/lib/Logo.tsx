/** Minimal geometric logomark: a spreadsheet grid with a checkmark, standing
 * in for "audited spreadsheet". Plain inline SVG (two colors, no gradients
 * or fine detail) so it also reads cleanly at favicon/extension-icon sizes
 * if it's promoted there later. Shared by the popup and the dashboard
 * header. */
export function Logo({ className = "", size = 24 }: { className?: string; size?: number }) {
  const padding = Math.round(size * 0.29); // matches the original fixed 24px icon / 7px padding ratio

  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-[6px] bg-white ${className}`}
      style={{ padding }}
    >
      <svg width={size} height={size} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <rect x="2" y="2" width="28" height="28" rx="6" stroke="#0B1120" strokeWidth="2.5" />
        <line x1="2" y1="12.5" x2="30" y2="12.5" stroke="#0B1120" strokeWidth="2" />
        <line x1="13" y1="2" x2="13" y2="30" stroke="#0B1120" strokeWidth="2" />
        <path
          d="M17.5 18.5L21 22L27.5 15"
          stroke="#4F7CFF"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}
