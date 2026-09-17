import type { ReactNode } from "react";

export function Panel({
  title,
  subtitle,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded border border-[var(--border)] bg-[var(--surface)] ${className}`}>
      <div className="flex items-baseline justify-between border-b border-[var(--border)] px-4 py-2">
        <h2 className="font-mono text-xs font-semibold uppercase tracking-widest text-neutral-400">
          {title}
        </h2>
        {subtitle ? <span className="font-mono text-[11px] text-neutral-600">{subtitle}</span> : null}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function KeyValueRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-[var(--border)] py-1.5 last:border-0">
      <span className="text-xs text-neutral-500">{label}</span>
      <span className="font-mono text-sm text-neutral-200">{value}</span>
    </div>
  );
}
