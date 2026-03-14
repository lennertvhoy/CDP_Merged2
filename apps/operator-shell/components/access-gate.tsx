"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, Loader2, LockKeyhole } from "lucide-react";

import type { OperatorShellAdapter } from "@/lib/adapters/operator-shell";
import type { BootstrapPayload } from "@/lib/types/operator";

export function AccessGate({
  adapter,
  session,
  onSessionChanged,
}: {
  adapter: OperatorShellAdapter;
  session: BootstrapPayload["session"];
  onSessionChanged: () => Promise<void>;
}) {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const usesLocalAccounts = session.auth.password_mode === "local-accounts";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !password || (usesLocalAccounts && !identifier.trim())) {
      return;
    }

    setPending(true);
    setError(null);
    try {
      await adapter.login(identifier.trim(), password);
      setPassword("");
      await onSessionChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to continue.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-10">
      <div className="w-full max-w-md rounded-[32px] border border-white/10 bg-black/55 p-8 shadow-[0_30px_120px_rgba(0,0,0,0.45)] backdrop-blur">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/95 text-black">
            <LockKeyhole size={18} />
          </div>
          <div>
            <p className="text-[11px] font-mono uppercase tracking-[0.18em] text-zinc-500">
              CDP_Merged
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-white">
              {session.gate?.title || "Private Access"}
            </h1>
          </div>
        </div>

        <p className="text-sm text-zinc-300">
          {session.gate?.subtitle || "This preview is temporarily protected while shared online."}
        </p>

        <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
          {usesLocalAccounts ? (
            <label className="block">
              <span className="mb-2 block text-[11px] font-mono uppercase tracking-[0.18em] text-zinc-500">
                Access email
              </span>
              <input
                value={identifier}
                onChange={(event) => setIdentifier(event.target.value)}
                placeholder="colleague@example.com"
                autoComplete="username"
                className="w-full rounded-2xl border border-white/10 bg-zinc-950/90 px-4 py-3 text-sm text-zinc-100 outline-none transition focus:border-zinc-500"
              />
            </label>
          ) : null}

          <label className="block">
            <span className="mb-2 block text-[11px] font-mono uppercase tracking-[0.18em] text-zinc-500">
              Access password
            </span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter password"
              autoComplete={usesLocalAccounts ? "current-password" : "off"}
              className="w-full rounded-2xl border border-white/10 bg-zinc-950/90 px-4 py-3 text-sm text-zinc-100 outline-none transition focus:border-zinc-500"
            />
          </label>

          <button
            type="submit"
            disabled={pending || !password || (usesLocalAccounts && !identifier.trim())}
            className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-white px-4 text-sm font-medium text-black transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:bg-zinc-800 disabled:text-zinc-500"
          >
            {pending ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
            {pending ? "Checking access" : "Continue"}
          </button>
        </form>

        <p className="mt-5 text-sm text-zinc-500">
          {session.gate?.help || "Enter the access password to continue."}
        </p>
        {error ? <p className="mt-3 text-sm text-rose-300">{error}</p> : null}
      </div>
    </main>
  );
}
