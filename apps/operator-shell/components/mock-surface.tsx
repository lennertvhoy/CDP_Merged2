"use client";

import { Database } from "lucide-react";

import { SectionHeader, SurfacePill } from "@/components/shell-primitives";
import type { MockSurfacePayload } from "@/lib/types/operator";

export function MockSurface({ payload }: { payload: MockSurfacePayload }) {
  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-[#050505]">
      <SectionHeader
        title={payload.title}
        detail={payload.detail}
        actions={<SurfacePill mode="mock" label="Mocked surface" />}
      />

      <div className="flex-1 overflow-y-auto px-8 py-8">
        <div className="mx-auto grid max-w-6xl gap-6 md:grid-cols-2 xl:grid-cols-3">
          {payload.cards.map((card) => (
            <article
              key={card.title}
              className="rounded-2xl border border-zinc-800 bg-[#0a0a0a] p-5"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-zinc-500">
                    {card.eyebrow}
                  </p>
                  <h2 className="mt-2 text-base font-medium text-zinc-100">{card.title}</h2>
                </div>
                <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-2 text-zinc-500">
                  <Database size={14} />
                </div>
              </div>

              <p className="mt-4 text-sm leading-6 text-zinc-400">{card.detail}</p>

              <div className="mt-4 flex flex-wrap gap-2">
                {card.badges.map((badge) => (
                  <span
                    key={badge}
                    className="rounded-full border border-zinc-800 bg-zinc-950 px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.16em] text-zinc-400"
                  >
                    {badge}
                  </span>
                ))}
              </div>

              <div className="mt-5 border-t border-zinc-800 pt-4 text-xs leading-5 text-zinc-500">
                {card.footer}
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
