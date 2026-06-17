import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold tracking-tight", className)}>
      <svg
        width="28"
        height="28"
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden
        className="shrink-0"
      >
        <defs>
          <linearGradient id="voyantra-mark" x1="0" y1="0" x2="32" y2="32">
            <stop offset="0%" stopColor="var(--color-brand-1)" />
            <stop offset="55%" stopColor="var(--color-brand-2)" />
            <stop offset="100%" stopColor="var(--color-brand-3)" />
          </linearGradient>
        </defs>
        <circle cx="16" cy="16" r="14" stroke="url(#voyantra-mark)" strokeWidth="2.5" />
        <path
          d="M16 6 L20 16 L16 26 L12 16 Z"
          fill="url(#voyantra-mark)"
          opacity="0.9"
        />
        <circle cx="16" cy="16" r="2.4" fill="var(--color-background)" />
      </svg>
      <span className="text-lg">Voyantra</span>
    </span>
  );
}
