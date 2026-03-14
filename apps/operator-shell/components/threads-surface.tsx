"use client";

import { useDeferredValue, useEffect, useState } from "react";
import { Loader2, MessageSquare, Search } from "lucide-react";

import {
  EmptyState,
  ErrorState,
  SectionHeader,
  SurfacePill,
} from "@/components/shell-primitives";
import { FeedbackButton } from "@/components/feedback-button";
import { formatRelativeDate } from "@/lib/formatters";
import type {
  OperatorShellAdapter,
} from "@/lib/adapters/operator-shell";
import type {
  SurfaceDescriptor,
  ThreadDetail,
  ThreadDetailPayload,
  ThreadListPayload,
} from "@/lib/types/operator";

export function ThreadsSurface({
  adapter,
  surface,
  authKey,
  onResumeThread,
}: {
  adapter: OperatorShellAdapter;
  surface: SurfaceDescriptor;
  authKey: string;
  onResumeThread: (thread: ThreadDetail) => void;
}) {
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [payload, setPayload] = useState<ThreadListPayload | null>(null);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ThreadDetailPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    void adapter
      .getThreads(deferredSearch)
      .then((result) => {
        if (!active) {
          return;
        }
        setPayload(result);
        setSelectedThreadId((current) => {
          const firstThreadId = result.threads[0]?.id ?? null;
          if (!current) {
            return firstThreadId;
          }
          return result.threads.some((thread) => thread.id === current) ? current : firstThreadId;
        });
      })
      .catch((reason: unknown) => {
        if (!active) {
          return;
        }
        setError(reason instanceof Error ? reason.message : "Failed to load threads.");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [adapter, authKey, deferredSearch]);

  useEffect(() => {
    if (!selectedThreadId || payload?.status !== "ok") {
      setDetail(null);
      return;
    }

    let active = true;
    setDetailLoading(true);
    setDetailError(null);

    void adapter
      .getThread(selectedThreadId)
      .then((result) => {
        if (active) {
          setDetail(result);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setDetailError(reason instanceof Error ? reason.message : "Failed to load thread detail.");
        }
      })
      .finally(() => {
        if (active) {
          setDetailLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [adapter, payload?.status, selectedThreadId]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-[#050505]">
      <SectionHeader
        title="Threads"
        detail="Open a recent conversation or continue it in chat."
        actions={
          <div className="flex items-center gap-3">
            <FeedbackButton
              adapter={adapter}
              surface="threads"
              threadId={selectedThreadId}
              context={{ search }}
              buttonLabel="Report thread issue"
            />
            <SurfacePill mode={surface.mode} />
          </div>
        }
      />

      <div className="flex-1 overflow-hidden px-8 py-8">
        <div className="grid h-full gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
          <div className="flex min-h-0 flex-col rounded-2xl border border-zinc-800 bg-[#0a0a0a]">
            <div className="border-b border-zinc-800 px-5 py-4">
              <label className="relative block">
                <Search
                  size={14}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600"
                />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search thread titles..."
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 py-2.5 pl-9 pr-4 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
                />
              </label>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
              {loading ? (
                <LoadingBlock label="Loading conversations..." />
              ) : error ? (
                <ErrorState title="Unable to load conversations" detail={error} />
              ) : payload?.status === "unavailable" ? (
                <EmptyState title="Conversations are unavailable" detail={payload.surface.message} />
              ) : payload?.surface.reason === "authentication_required" ? (
                <EmptyState
                  title="Sign in to view your conversations"
                  detail={payload.surface.message}
                />
              ) : payload && payload.threads.length === 0 ? (
                <EmptyState
                  title="No conversations yet"
                  detail="Start chatting to create your first saved conversation."
                />
              ) : (
                <div className="space-y-3">
                  {payload?.threads.map((thread) => {
                    const selected = thread.id === selectedThreadId;
                    return (
                      <button
                        key={thread.id}
                        type="button"
                        onClick={() => setSelectedThreadId(thread.id)}
                        className={`w-full rounded-2xl border p-4 text-left transition ${
                          selected
                            ? "border-blue-500/30 bg-blue-500/5"
                            : "border-zinc-800 bg-zinc-950 hover:border-zinc-700"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="space-y-1">
                            <h2 className="text-sm font-medium text-zinc-100">{thread.title}</h2>
                            <p className="text-xs text-zinc-500">
                              {thread.preview || "No preview stored yet."}
                            </p>
                          </div>
                          <span className="text-[11px] font-mono text-zinc-500">
                            {formatRelativeDate(thread.updated_at)}
                          </span>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2 text-[10px] font-mono uppercase tracking-[0.14em] text-zinc-500">
                          <span className="rounded-full border border-zinc-800 px-2 py-1">
                            {thread.user_messages} user turns
                          </span>
                          <span className="rounded-full border border-zinc-800 px-2 py-1">
                            {thread.total_steps} steps
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <div className="min-h-0 rounded-2xl border border-zinc-800 bg-[#0a0a0a]">
            <div className="border-b border-zinc-800 px-5 py-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-medium text-zinc-100">
                  <MessageSquare size={15} className="text-zinc-500" />
                  Conversation details
                </div>
                <FeedbackButton
                  adapter={adapter}
                  surface="threads.detail"
                  threadId={selectedThreadId}
                  context={{ selected_thread_id: selectedThreadId }}
                  buttonLabel="Share feedback"
                  buttonClassName="inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-600"
                />
              </div>
            </div>

            <div className="min-h-0 max-h-full overflow-y-auto px-5 py-5">
              {detailLoading ? (
                <LoadingBlock label="Loading conversation..." />
              ) : detailError ? (
                <ErrorState title="Unable to load conversation" detail={detailError} />
              ) : detail?.thread ? (
                <div className="space-y-5">
                  <div>
                    <h2 className="text-lg font-medium text-zinc-100">{detail.thread.title}</h2>
                    <p className="mt-1 text-xs font-mono uppercase tracking-[0.16em] text-zinc-500">
                      Updated {formatRelativeDate(detail.thread.updated_at)}
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={() => onResumeThread(detail.thread!)}
                    className="inline-flex items-center justify-center rounded-full border border-zinc-700 bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950 transition hover:bg-white"
                  >
                    Resume in chat
                  </button>

                  <div className="space-y-3">
                    {detail.thread.steps.length === 0 ? (
                      <EmptyState
                        title="No messages stored"
                        detail="This conversation exists, but no message details are available yet."
                      />
                    ) : (
                      detail.thread.steps.map((step) => (
                        <article
                          key={step.id}
                          className="rounded-2xl border border-zinc-800 bg-zinc-950 p-4"
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div>
                              <p className="text-sm font-medium text-zinc-100">
                                {step.name || step.type || "Step"}
                              </p>
                              <p className="mt-1 text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">
                                {formatRelativeDate(step.created_at)}
                              </p>
                            </div>
                            {step.is_error ? (
                              <span className="rounded-full border border-rose-500/20 bg-rose-500/10 px-2 py-1 text-[10px] font-mono uppercase tracking-[0.16em] text-rose-300">
                                error
                              </span>
                            ) : null}
                          </div>
                          {step.input ? (
                            <p className="mt-4 rounded-xl border border-zinc-800 bg-[#050505] p-3 text-sm text-zinc-300">
                              {step.input}
                            </p>
                          ) : null}
                          {step.output ? (
                            <p className="mt-3 rounded-xl border border-zinc-800 bg-[#050505] p-3 text-sm text-zinc-400">
                              {step.output}
                            </p>
                          ) : null}
                        </article>
                      ))
                    )}
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="Select a conversation"
                  detail="Choose a conversation from the list to open it here."
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="flex min-h-[240px] flex-col items-center justify-center gap-3 text-zinc-500">
      <Loader2 size={22} className="animate-spin" />
      <p className="text-sm">{label}</p>
    </div>
  );
}
