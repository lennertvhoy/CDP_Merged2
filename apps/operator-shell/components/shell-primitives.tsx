import type { ReactNode } from "react";

export function SurfacePill({
  mode,
  label,
}: {
  mode: "backend" | "mock";
  label?: string;
}) {
  const resolvedLabel = label ?? (mode === "backend" ? "Backend" : "Mock");
  const className =
    mode === "backend"
      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
      : "border-amber-500/20 bg-amber-500/10 text-amber-300";

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.18em] ${className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {resolvedLabel}
    </span>
  );
}

export function SectionHeader({
  title,
  detail,
  actions,
}: {
  title: string;
  detail: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-6 border-b border-zinc-800/80 px-8 py-6">
      <div className="space-y-1">
        <h1 className="text-xl font-medium text-zinc-100">{title}</h1>
        <p className="max-w-3xl text-sm text-zinc-500">{detail}</p>
      </div>
      {actions}
    </div>
  );
}

export function EmptyState({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-zinc-800 bg-zinc-900/30 px-6 py-20 text-center">
      <h2 className="text-lg font-medium text-zinc-100">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm text-zinc-500">{detail}</p>
    </div>
  );
}

export function ErrorState({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 px-6 py-20 text-center">
      <h2 className="text-lg font-medium text-rose-300">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm text-zinc-400">{detail}</p>
    </div>
  );
}
