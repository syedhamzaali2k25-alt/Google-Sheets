function WarningIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true" className="shrink-0">
      <path d="M10 3.5 17.5 16h-15L10 3.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M10 8.5v3.2M10 14v.01" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2.5 rounded-control border border-critical-tint-border bg-critical-tint p-4 text-sm text-critical-500">
      <WarningIcon />
      <p>{message}</p>
    </div>
  );
}
