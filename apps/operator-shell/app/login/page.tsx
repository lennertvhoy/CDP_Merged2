"use client";

import Link from "next/link";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-950 px-6 text-zinc-100">
      <div className="w-full max-w-lg rounded-3xl border border-zinc-800 bg-zinc-900/80 p-8 shadow-2xl shadow-black/30">
        <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-zinc-500">Private preview</p>
        <h1 className="mt-3 text-2xl font-semibold text-white">Use the main access screen</h1>
        <p className="mt-3 text-sm text-zinc-300">
          This preview now uses the access gate on the home page instead of a separate login route.
        </p>
        <Link
          href="/"
          className="mt-6 inline-flex h-[42px] items-center justify-center rounded-full border border-zinc-700 bg-zinc-100 px-4 text-sm font-medium text-zinc-950 transition hover:bg-white"
        >
          Return to preview
        </Link>
      </div>
    </main>
  );
}
