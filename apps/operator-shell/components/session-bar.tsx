"use client";

import { useState } from "react";
import { Loader2, LogOut } from "lucide-react";

import type { OperatorShellAdapter } from "@/lib/adapters/operator-shell";
import type { BootstrapPayload } from "@/lib/types/operator";

export function SessionBar({
  adapter,
  session,
  onSessionChanged,
}: {
  adapter: OperatorShellAdapter;
  session: BootstrapPayload["session"];
  onSessionChanged: () => Promise<void>;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLogout() {
    setPending(true);
    setError(null);
    try {
      await adapter.logout();
      await onSessionChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign-out failed.");
    } finally {
      setPending(false);
    }
  }

  if (!session.auth.required) {
    return (
      <div className="border-b border-zinc-800/80 bg-[#080808] px-8 py-4">
        <div className="flex items-center gap-3 text-sm text-zinc-500">
          Preview access is disabled for this local runtime.
        </div>
      </div>
    );
  }

  return (
    <div className="border-b border-zinc-800/80 bg-[#080808] px-8 py-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-zinc-500">
            Private preview
          </p>
          <p className="mt-1 text-sm text-zinc-200">{session.detail}</p>
        </div>
        <button
          type="button"
          onClick={() => void handleLogout()}
          disabled={pending}
          className="inline-flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-950 px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 disabled:cursor-not-allowed disabled:border-zinc-800 disabled:text-zinc-500"
        >
          {pending ? <Loader2 size={14} className="animate-spin" /> : <LogOut size={14} />}
          {pending ? "Signing out" : "Sign out"}
        </button>
      </div>
      {error ? <p className="mt-3 text-sm text-rose-300">{error}</p> : null}
    </div>
  );
}
