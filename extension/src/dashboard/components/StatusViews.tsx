export function ErrorBanner({ message }: { message: string }) {
  return <div className="rounded-[4px] border border-[#F3C6C0] bg-[#FDE9E7] p-4 text-sm text-[#C0281C]">{message}</div>;
}
