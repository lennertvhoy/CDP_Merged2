"use client";

import { Fragment, type ReactNode, useEffect, useRef, useState } from "react";
import {
  BarChart3,
  ChevronDown,
  FileSpreadsheet,
  FolderPlus,
  Loader2,
  Send,
  TerminalSquare,
} from "lucide-react";

import { FeedbackButton } from "@/components/feedback-button";
import { SectionHeader, SurfacePill } from "@/components/shell-primitives";
import type { OperatorShellAdapter } from "@/lib/adapters/operator-shell";
import type {
  BootstrapPayload,
  ChatSuggestedAction,
  ThreadDetail,
} from "@/lib/types/operator";

type TranscriptMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  status: "complete" | "streaming" | "error";
  toolCalls?: string[];
  suggestedActions?: ChatSuggestedAction[];
};

type ContentBlock =
  | {
      type: "paragraph";
      content: string;
      tone: "answer" | "note" | "body";
    }
  | {
      type: "bullet_list";
      items: string[];
    };

const TOOL_LABELS: Record<string, string> = {
  aggregate_profiles: "Aggregation breakdown",
  create_data_artifact: "Report export",
  create_segment: "Segment creation",
  export_segment_to_csv: "CSV export",
  get_data_coverage_stats: "Coverage lookup",
  get_geographic_revenue_distribution: "Revenue distribution",
  get_identity_link_quality: "Identity-link quality",
  get_industry_summary: "Industry summary",
  get_segment_stats: "Segment stats",
  query_unified_360: "360 lookup",
  search_profiles: "Company search",
};

function createLocalId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `local-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isSuggestedActionArray(value: unknown): value is ChatSuggestedAction[] {
  return (
    Array.isArray(value) &&
    value.every(
      (entry) =>
        typeof entry === "object" &&
        entry !== null &&
        typeof entry.id === "string" &&
        typeof entry.label === "string" &&
        typeof entry.prompt === "string",
    )
  );
}

function extractToolCalls(metadata: Record<string, unknown> | undefined): string[] | undefined {
  const rawToolCalls = metadata?.tool_calls;
  if (!Array.isArray(rawToolCalls)) {
    return undefined;
  }

  const toolCalls = rawToolCalls.filter((entry): entry is string => typeof entry === "string");
  return toolCalls.length > 0 ? toolCalls : undefined;
}

function extractSuggestedActions(
  metadata: Record<string, unknown> | undefined,
): ChatSuggestedAction[] | undefined {
  const rawActions = metadata?.suggested_actions;
  return isSuggestedActionArray(rawActions) && rawActions.length > 0 ? rawActions : undefined;
}

function buildTranscriptFromThread(thread: ThreadDetail): TranscriptMessage[] {
  return thread.steps.flatMap((step) => {
    const createdAt = step.created_at;
    const messages: TranscriptMessage[] = [];
    const toolCalls = extractToolCalls(step.metadata);
    const suggestedActions = extractSuggestedActions(step.metadata);

    if (step.type === "user_message" && step.input) {
      messages.push({
        id: `${step.id}-user`,
        role: "user",
        content: step.input,
        createdAt,
        status: "complete",
      });
    }

    if (step.type === "assistant_message" && step.output) {
      messages.push({
        id: `${step.id}-assistant`,
        role: "assistant",
        content: step.output,
        createdAt,
        status: step.is_error ? "error" : "complete",
        toolCalls,
        suggestedActions,
      });
    }

    return messages;
  });
}

function parseContentBlocks(content: string): ContentBlock[] {
  const normalized = content.replace(/\r\n/g, "\n").trim();
  if (!normalized) {
    return [];
  }

  const rawBlocks = normalized.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean);
  return rawBlocks.map((block, index) => {
    const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
    const bulletLines = lines
      .map((line) => {
        const match = /^[-*]\s+(.*)$/.exec(line);
        return match ? match[1] : null;
      })
      .filter((line): line is string => Boolean(line));

    if (bulletLines.length === lines.length && bulletLines.length > 0) {
      return {
        type: "bullet_list",
        items: bulletLines,
      } satisfies ContentBlock;
    }

    const paragraph = lines.join(" ");
    const lowered = paragraph.toLowerCase();
    const tone =
      index === 0
        ? "answer"
        : lowered.startsWith("**let op:**") ||
            lowered.startsWith("let op:") ||
            lowered.startsWith("**note:**") ||
            lowered.startsWith("note:") ||
            lowered.startsWith("**attention")
          ? "note"
          : "body";

    return {
      type: "paragraph",
      content: paragraph,
      tone,
    } satisfies ContentBlock;
  });
}

function renderInlineText(text: string): ReactNode[] {
  return text
    .split(/(\*\*[^*]+\*\*)/g)
    .filter(Boolean)
    .map((segment, index) =>
      segment.startsWith("**") && segment.endsWith("**") ? (
        <strong key={`${segment}-${index}`} className="font-semibold text-zinc-100">
          {segment.slice(2, -2)}
        </strong>
      ) : (
        <Fragment key={`${segment}-${index}`}>{segment}</Fragment>
      ),
    );
}

function friendlyToolLabel(toolName: string): string {
  return TOOL_LABELS[toolName] ?? toolName.replaceAll("_", " ");
}

function actionIcon(actionId: string) {
  if (actionId === "create_segment") {
    return <FolderPlus size={14} />;
  }
  if (actionId === "export_csv") {
    return <FileSpreadsheet size={14} />;
  }
  return <BarChart3 size={14} />;
}

function StreamingIndicator() {
  return (
    <div className="flex items-center gap-1.5 py-1">
      <span className="h-2 w-2 animate-pulse rounded-full bg-zinc-500 [animation-delay:0ms]" />
      <span className="h-2 w-2 animate-pulse rounded-full bg-zinc-500 [animation-delay:150ms]" />
      <span className="h-2 w-2 animate-pulse rounded-full bg-zinc-500 [animation-delay:300ms]" />
    </div>
  );
}

export function ChatSurface({
  adapter,
  bootstrap,
  resumeThread,
}: {
  adapter: OperatorShellAdapter;
  bootstrap: BootstrapPayload | null;
  resumeThread: ThreadDetail | null;
}) {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  useEffect(() => {
    if (!resumeThread) {
      return;
    }

    setThreadId(resumeThread.id);
    setMessages(buildTranscriptFromThread(resumeThread));
    setError(null);
  }, [resumeThread]);

  useEffect(() => {
    if (bootstrap?.session.auth.required && !bootstrap.session.authenticated) {
      setThreadId(null);
      setMessages([]);
      setError(null);
    }
  }, [bootstrap?.session.auth.required, bootstrap?.session.authenticated]);

  async function submitMessage(messageText: string) {
    const message = messageText.trim();
    if (!message || isStreaming) {
      return;
    }

    const userMessageId = createLocalId();
    const assistantMessageId = createLocalId();

    setDraft("");
    setError(null);
    setIsStreaming(true);
    setMessages((current) => [
      ...current,
      {
        id: userMessageId,
        role: "user",
        content: message,
        createdAt: new Date().toISOString(),
        status: "complete",
      },
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        createdAt: new Date().toISOString(),
        status: "streaming",
      },
    ]);

    let authoritativeThreadId = threadId;

    try {
      for await (const event of adapter.streamChatTurn({
        message,
        thread_id: authoritativeThreadId,
      })) {
        if (event.type === "thread") {
          authoritativeThreadId = event.thread_id;
          setThreadId(event.thread_id);
        } else if (event.type === "assistant_delta") {
          setMessages((current) =>
            current.map((entry) =>
              entry.id === assistantMessageId
                ? {
                    ...entry,
                    content: `${entry.content}${event.delta}`,
                    status: "streaming",
                  }
                : entry,
            ),
          );
        } else if (event.type === "assistant_message") {
          authoritativeThreadId = event.thread_id;
          setThreadId(event.thread_id);
          setMessages((current) =>
            current.map((entry) =>
              entry.id === assistantMessageId
                ? {
                    ...entry,
                    content: event.message.content,
                    createdAt: event.message.created_at,
                    status: event.message.status === "error" ? "error" : "complete",
                    toolCalls: event.tool_calls,
                    suggestedActions: event.suggested_actions ?? [],
                  }
                : entry,
            ),
          );
        } else if (event.type === "error") {
          setError(event.error);
          if (event.thread_id) {
            authoritativeThreadId = event.thread_id;
            setThreadId(event.thread_id);
          }
          setMessages((current) =>
            current.map((entry) =>
              entry.id === assistantMessageId
                ? {
                    ...entry,
                    content: event.error,
                    status: "error",
                  }
                : entry,
            ),
          );
        }
      }
    } catch (reason) {
      const detail =
        reason instanceof Error ? reason.message : "The runtime stream failed unexpectedly.";
      setError(detail);
      setMessages((current) =>
        current.map((entry) =>
          entry.id === assistantMessageId
            ? {
                ...entry,
                content: detail,
                status: "error",
              }
            : entry,
        ),
      );
    } finally {
      setIsStreaming(false);
    }
  }

  function handleSubmit() {
    void submitMessage(draft);
  }

  function handleSuggestedAction(prompt: string) {
    void submitMessage(prompt);
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-[#050505]">
      <SectionHeader
        title="Chat"
        detail="Ask a question, review the answer, and continue from the same saved conversation."
        actions={
          <div className="flex items-center gap-3">
            <FeedbackButton
              adapter={adapter}
              surface="chat"
              threadId={threadId}
              context={{ message_count: messages.length, streaming: isStreaming }}
              buttonLabel="Report chat issue"
            />
            <SurfacePill mode="backend" label="Live" />
          </div>
        }
      />

      <div className="flex flex-1 overflow-hidden px-6 py-6">
        <div className="mx-auto flex min-h-0 w-full max-w-[72rem] flex-col rounded-[28px] border border-zinc-800 bg-[#0a0a0a]">
          <div className="border-b border-zinc-800 px-5 py-3.5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-950 text-zinc-400">
                  <TerminalSquare size={16} />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium text-zinc-100">Conversation</div>
                  <p className="mt-1 text-[11px] font-medium uppercase tracking-[0.16em] text-zinc-500">
                    {threadId ? "Saved conversation" : "New conversation"}
                  </p>
                  <p className="mt-1 text-xs text-zinc-500">
                    {threadId
                      ? "Replies and follow-up actions stay attached to this thread automatically."
                      : "Your first completed answer will create a saved thread automatically."}
                  </p>
                </div>
              </div>
              <FeedbackButton
                adapter={adapter}
                surface="chat.conversation"
                threadId={threadId}
                context={{ message_count: messages.length, has_result: messages.length > 0 }}
                buttonLabel="Share feedback"
                buttonClassName="inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-600"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-4">
            {messages.length === 0 ? (
              <div className="rounded-[22px] border border-dashed border-zinc-800 bg-zinc-950/70 px-5 py-5">
                <p className="max-w-2xl text-sm leading-6 text-zinc-300">
                  Start the conversation here. Once the first answer is complete, the thread stays
                  available in the Threads tab so you can resume it later.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {messages.map((message) => (
                  <ChatBubble
                    key={message.id}
                    message={message}
                    pending={isStreaming}
                    onSuggestedAction={handleSuggestedAction}
                  />
                ))}
              </div>
            )}
            <div ref={transcriptEndRef} />
          </div>

          <div className="border-t border-zinc-800 px-5 py-4">
            <form
              className="space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                handleSubmit();
              }}
            >
              <label className="block">
                <span className="sr-only">Message</span>
                <textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      handleSubmit();
                    }
                  }}
                  rows={3}
                  placeholder="Ask a question, continue this conversation, or start a new topic..."
                  className="w-full resize-none rounded-[22px] border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
                />
              </label>
              <div className="flex items-center justify-between gap-3">
                <div className="text-[11px] text-zinc-500">
                  {error ? error : "Press Enter to send. Use Shift+Enter for a new line."}
                </div>
                <button
                  type="submit"
                  disabled={isStreaming || !draft.trim()}
                  className="inline-flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950 transition hover:bg-white disabled:cursor-not-allowed disabled:border-zinc-800 disabled:bg-zinc-900 disabled:text-zinc-500"
                >
                  {isStreaming ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                  {isStreaming ? "Working" : "Send"}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChatBubble({
  message,
  pending,
  onSuggestedAction,
}: {
  message: TranscriptMessage;
  pending: boolean;
  onSuggestedAction: (prompt: string) => void;
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[70ch] rounded-[22px] bg-zinc-800 px-4 py-3 text-sm leading-6 text-zinc-100">
          {message.content}
        </div>
      </div>
    );
  }

  const bubbleClass =
    message.status === "error"
      ? "border-rose-500/20 bg-rose-500/5 text-rose-200"
      : "border-zinc-800 bg-zinc-950 text-zinc-300";
  const blocks = parseContentBlocks(message.content);

  return (
    <div className="flex justify-start">
      <div className={`max-w-[78ch] rounded-[24px] border px-4 py-3.5 text-sm ${bubbleClass}`}>
        {message.status === "streaming" ? (
          <StreamingIndicator />
        ) : (
          <div className="space-y-3">
            {blocks.length > 0 ? (
              blocks.map((block, index) => {
                if (block.type === "bullet_list") {
                  return (
                    <ul key={`list-${index}`} className="space-y-2 pl-4 text-sm leading-6 text-zinc-300">
                      {block.items.map((item, itemIndex) => (
                        <li key={`item-${itemIndex}`} className="list-disc">
                          {renderInlineText(item)}
                        </li>
                      ))}
                    </ul>
                  );
                }

                const className =
                  block.tone === "answer"
                    ? "text-[15px] font-medium leading-7 text-zinc-100"
                    : block.tone === "note"
                      ? "rounded-2xl border border-amber-500/15 bg-amber-500/5 px-3 py-2 text-sm leading-6 text-zinc-200"
                      : "text-sm leading-6 text-zinc-300";

                return (
                  <p key={`paragraph-${index}`} className={className}>
                    {renderInlineText(block.content)}
                  </p>
                );
              })
            ) : (
              <p className="text-sm leading-6 text-zinc-300">{message.content}</p>
            )}
          </div>
        )}

        {message.status !== "streaming" && message.suggestedActions && message.suggestedActions.length > 0 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {message.suggestedActions.map((action, index) => (
              <button
                key={action.id}
                type="button"
                onClick={() => onSuggestedAction(action.prompt)}
                disabled={pending}
                className={
                  index === 0
                    ? "inline-flex items-center gap-2 rounded-full border border-zinc-100 bg-zinc-100 px-3.5 py-2 text-sm font-medium text-zinc-950 transition hover:bg-white disabled:cursor-not-allowed disabled:border-zinc-800 disabled:bg-zinc-900 disabled:text-zinc-500"
                    : "inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-[#121212] px-3.5 py-2 text-sm font-medium text-zinc-200 transition hover:border-zinc-700 hover:bg-zinc-900 disabled:cursor-not-allowed disabled:border-zinc-800 disabled:text-zinc-500"
                }
              >
                {actionIcon(action.id)}
                {action.label}
              </button>
            ))}
          </div>
        ) : null}

        {message.status !== "streaming" && message.toolCalls && message.toolCalls.length > 0 ? (
          <details className="mt-3 rounded-2xl border border-zinc-800/80 bg-[#0c0c0c] px-3 py-2 text-xs text-zinc-500">
            <summary className="flex cursor-pointer list-none items-center gap-2 font-medium text-zinc-400">
              <ChevronDown size={14} className="transition" />
              Details
            </summary>
            <div className="mt-2 space-y-2">
              <p className="text-[11px] uppercase tracking-[0.14em] text-zinc-500">
                Used for this answer
              </p>
              <div className="flex flex-wrap gap-2">
                {message.toolCalls.map((toolCall, index) => (
                  <span
                    key={`${toolCall}-${index}`}
                    className="rounded-full border border-zinc-800 px-2 py-1 text-[11px] text-zinc-400"
                  >
                    {friendlyToolLabel(toolCall)}
                  </span>
                ))}
              </div>
            </div>
          </details>
        ) : null}
      </div>
    </div>
  );
}
