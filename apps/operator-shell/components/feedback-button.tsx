"use client";

import { type FormEvent, useMemo, useState } from "react";
import { MessageSquareWarning, Paperclip, Send, X } from "lucide-react";

import type { OperatorShellAdapter } from "@/lib/adapters/operator-shell";
import type { FeedbackSubmissionResult } from "@/lib/types/operator";

type FeedbackButtonProps = {
  adapter: OperatorShellAdapter;
  surface: string;
  threadId?: string | null;
  companyRef?: string | null;
  segmentRef?: string | null;
  context?: Record<string, unknown>;
  buttonLabel?: string;
  buttonClassName?: string;
};

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function FeedbackButton({
  adapter,
  surface,
  threadId,
  companyRef,
  segmentRef,
  context,
  buttonLabel = "Share feedback",
  buttonClassName,
}: FeedbackButtonProps) {
  const [open, setOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [screenshots, setScreenshots] = useState<File[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FeedbackSubmissionResult | null>(null);

  const normalizedContext = useMemo(
    () => ({
      ...context,
      shell_surface: surface,
      thread_id: threadId ?? null,
      company_ref: companyRef ?? null,
      segment_ref: segmentRef ?? null,
    }),
    [companyRef, context, segmentRef, surface, threadId],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !feedbackText.trim()) {
      return;
    }

    setPending(true);
    setError(null);

    try {
      const submission = await adapter.submitFeedback({
        surface,
        feedbackText: feedbackText.trim(),
        pagePath: window.location.pathname,
        pageUrl: window.location.href,
        threadId,
        companyRef,
        segmentRef,
        screenshots,
        context: {
          ...normalizedContext,
          browser: {
            user_agent: navigator.userAgent,
            language: navigator.language,
            viewport: {
              width: window.innerWidth,
              height: window.innerHeight,
            },
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          },
          client_timestamp: new Date().toISOString(),
        },
      });
      setResult(submission);
      setFeedbackText("");
      setScreenshots([]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Feedback submission failed.");
    } finally {
      setPending(false);
    }
  }

  function closeModal() {
    if (pending) {
      return;
    }
    setOpen(false);
    setError(null);
    setResult(null);
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={
          buttonClassName ??
          "inline-flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-950 px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500"
        }
      >
        <MessageSquareWarning size={14} />
        {buttonLabel}
      </button>

      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-8">
          <div className="w-full max-w-2xl rounded-[28px] border border-zinc-800 bg-[#090909] shadow-[0_30px_100px_rgba(0,0,0,0.55)]">
            <div className="flex items-start justify-between gap-6 border-b border-zinc-800 px-6 py-5">
              <div>
                <p className="text-[11px] font-mono uppercase tracking-[0.18em] text-zinc-500">
                  Operator feedback
                </p>
                <h2 className="mt-1 text-xl font-medium text-zinc-100">Be specific about what broke</h2>
                <p className="mt-2 max-w-xl text-sm text-zinc-400">
                  Include what you expected, what actually happened, and the smallest repro you can give.
                  Add a screenshot when the shell state or reply is easier to show than explain.
                </p>
              </div>
              <button
                type="button"
                onClick={closeModal}
                className="rounded-full border border-zinc-800 p-2 text-zinc-400 transition hover:border-zinc-700 hover:text-zinc-200"
              >
                <X size={16} />
              </button>
            </div>

            <form className="space-y-5 px-6 py-6" onSubmit={handleSubmit}>
              <div className="grid gap-3 rounded-2xl border border-zinc-800 bg-zinc-950/70 p-4 text-xs text-zinc-500 md:grid-cols-2">
                <div>
                  <span className="font-mono uppercase tracking-[0.16em] text-zinc-600">Surface</span>
                  <p className="mt-1 text-sm text-zinc-300">{surface}</p>
                </div>
                <div>
                  <span className="font-mono uppercase tracking-[0.16em] text-zinc-600">Thread</span>
                  <p className="mt-1 truncate text-sm text-zinc-300">{threadId || "Not attached"}</p>
                </div>
              </div>

              <label className="block">
                <span className="mb-2 block text-[11px] font-mono uppercase tracking-[0.18em] text-zinc-500">
                  Feedback
                </span>
                <textarea
                  value={feedbackText}
                  onChange={(event) => setFeedbackText(event.target.value)}
                  rows={7}
                  placeholder="Be specific: what were you trying to do, what did you expect, what happened instead, and how could we reproduce it?"
                  className="w-full resize-none rounded-[24px] border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
                />
              </label>

              <label className="block">
                <span className="mb-2 block text-[11px] font-mono uppercase tracking-[0.18em] text-zinc-500">
                  Screenshots
                </span>
                <div className="rounded-[24px] border border-dashed border-zinc-700 bg-zinc-950/60 p-4">
                  <label className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-zinc-700 bg-[#111] px-3.5 py-2 text-sm text-zinc-200 transition hover:border-zinc-500">
                    <Paperclip size={14} />
                    Add screenshot
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      className="hidden"
                      onChange={(event) =>
                        setScreenshots(Array.from(event.target.files ?? []).slice(0, 3))
                      }
                    />
                  </label>
                  <p className="mt-3 text-xs text-zinc-500">Up to 3 image files, 5 MB each.</p>
                  {screenshots.length > 0 ? (
                    <ul className="mt-4 space-y-2">
                      {screenshots.map((file) => (
                        <li
                          key={`${file.name}-${file.size}`}
                          className="rounded-2xl border border-zinc-800 bg-black/30 px-3 py-2 text-sm text-zinc-300"
                        >
                          {file.name} · {formatBytes(file.size)}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </label>

              {result ? (
                <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                  Feedback saved as <code>{result.feedback_id}</code>. Evaluation:{" "}
                  <strong>{result.evaluation_status}</strong>. Notification:{" "}
                  <strong>{result.notification_status}</strong>.
                </div>
              ) : null}
              {error ? (
                <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                  {error}
                </div>
              ) : null}

              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-zinc-500">
                  The app sends your text, current surface, URL, optional thread reference, and safe runtime
                  context to the backend.
                </p>
                <button
                  type="submit"
                  disabled={pending || !feedbackText.trim()}
                  className="inline-flex items-center gap-2 rounded-full border border-zinc-100 bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950 transition hover:bg-white disabled:cursor-not-allowed disabled:border-zinc-800 disabled:bg-zinc-900 disabled:text-zinc-500"
                >
                  <Send size={14} />
                  {pending ? "Submitting" : "Send feedback"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </>
  );
}
