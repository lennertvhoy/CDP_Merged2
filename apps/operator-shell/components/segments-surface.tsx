"use client";

import { useDeferredValue, useEffect, useState, useTransition } from "react";
import { Download, Filter, Loader2, Plus, Search } from "lucide-react";

import {
  EmptyState,
  ErrorState,
  SectionHeader,
  SurfacePill,
} from "@/components/shell-primitives";
import { FeedbackButton } from "@/components/feedback-button";
import { formatRelativeDate } from "@/lib/formatters";
import type { OperatorShellAdapter } from "@/lib/adapters/operator-shell";
import type {
  CreateSegmentInput,
  SegmentDetailPayload,
  SegmentExportResult,
  SegmentListPayload,
  SurfaceDescriptor,
} from "@/lib/types/operator";

const EMPTY_CREATE_FORM: CreateSegmentInput = {
  name: "",
  description: "",
  keywords: "",
  city: "",
  status: "",
  has_email: true,
  has_phone: false,
  email_domain: "",
};

export function SegmentsSurface({
  adapter,
  surface,
}: {
  adapter: OperatorShellAdapter;
  surface: SurfaceDescriptor;
}) {
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [payload, setPayload] = useState<SegmentListPayload | null>(null);
  const [detail, setDetail] = useState<SegmentDetailPayload | null>(null);
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<CreateSegmentInput>(EMPTY_CREATE_FORM);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [isCreating, startCreateTransition] = useTransition();

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    void adapter
      .getSegments(deferredSearch)
      .then((result) => {
        if (!active) {
          return;
        }
        setPayload(result);
        setSelectedSegmentId((current) => current ?? result.segments[0]?.id ?? null);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Failed to load segments.");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [adapter, deferredSearch, refreshKey]);

  useEffect(() => {
    if (!selectedSegmentId) {
      setDetail(null);
      return;
    }

    let active = true;
    setDetailLoading(true);
    setDetailError(null);

    void adapter
      .getSegment(selectedSegmentId)
      .then((result) => {
        if (active) {
          setDetail(result);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setDetailError(reason instanceof Error ? reason.message : "Failed to load segment detail.");
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
  }, [adapter, selectedSegmentId, refreshKey]);

  function updateCreateField<Key extends keyof CreateSegmentInput>(
    key: Key,
    value: CreateSegmentInput[Key],
  ) {
    setCreateForm((current) => ({ ...current, [key]: value }));
  }

  function handleCreateSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);

    startCreateTransition(() => {
      void adapter
        .createSegment(createForm)
        .then((result) => {
          setShowCreateForm(false);
          setCreateForm(EMPTY_CREATE_FORM);
          setSelectedSegmentId(result.segment.segment_id);
          setRefreshKey((current) => current + 1);
        })
        .catch((reason: unknown) => {
          setCreateError(reason instanceof Error ? reason.message : "Failed to create segment.");
        });
    });
  }

  function handleExport() {
    if (!selectedSegmentId) {
      return;
    }

    setExporting(true);
    setExportMessage(null);

    void adapter
      .exportSegment(selectedSegmentId)
      .then((result: SegmentExportResult) => {
        setExportMessage(`${result.exported_count} rows exported.`);
        window.open(result.download_url, "_blank", "noopener,noreferrer");
      })
      .catch((reason: unknown) => {
        setExportMessage(reason instanceof Error ? reason.message : "Export failed.");
      })
      .finally(() => {
        setExporting(false);
      });
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-[#050505]">
      <SectionHeader
        title="Segments"
        detail="Create, review, and export saved segments."
        actions={
          <div className="flex items-center gap-3">
            <FeedbackButton
              adapter={adapter}
              surface="segments"
              segmentRef={selectedSegmentId}
              context={{ search, selected_segment_id: selectedSegmentId }}
              buttonLabel="Report segment issue"
            />
            <button
              type="button"
              onClick={() => setShowCreateForm((current) => !current)}
              className="inline-flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-950 px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-700 hover:bg-zinc-900"
            >
              <Plus size={14} />
              Create segment
            </button>
            <SurfacePill mode={surface.mode} />
          </div>
        }
      />

      <div className="flex-1 overflow-hidden px-8 py-8">
        <div className="grid h-full gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(380px,0.9fr)]">
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
                  placeholder="Search segments..."
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 py-2.5 pl-9 pr-4 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
                />
              </label>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
              {showCreateForm ? (
                <CreateSegmentForm
                  value={createForm}
                  pending={isCreating}
                  error={createError}
                  onChange={updateCreateField}
                  onSubmit={handleCreateSubmit}
                />
              ) : null}

              {loading ? (
                <LoadingBlock label="Loading segments..." />
              ) : error ? (
                <ErrorState title="Unable to load segments" detail={error} />
              ) : payload && payload.segments.length === 0 ? (
                <EmptyState
                  title="No segments found"
                  detail="Create a segment or adjust the search."
                />
              ) : (
                <div className="space-y-3">
                  {payload?.segments.map((segment) => {
                    const selected = selectedSegmentId === segment.id;
                    return (
                      <button
                        key={segment.id}
                        type="button"
                        onClick={() => setSelectedSegmentId(segment.id)}
                        className={`w-full rounded-2xl border p-4 text-left transition ${
                          selected
                            ? "border-indigo-500/30 bg-indigo-500/5"
                            : "border-zinc-800 bg-zinc-950 hover:border-zinc-700"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="space-y-1">
                            <h2 className="text-sm font-medium text-zinc-100">{segment.name}</h2>
                            <p className="text-xs text-zinc-500">
                              {segment.description || "No description stored."}
                            </p>
                          </div>
                          <span className="rounded-full border border-zinc-800 px-2 py-1 text-[10px] font-mono uppercase tracking-[0.16em] text-zinc-400">
                            {segment.member_count} members
                          </span>
                        </div>

                        <div className="mt-3 flex flex-wrap gap-2 text-[10px] font-mono uppercase tracking-[0.16em] text-zinc-500">
                          <span className="rounded-full border border-zinc-800 px-2 py-1">
                            {segment.segment_key}
                          </span>
                          <span className="rounded-full border border-zinc-800 px-2 py-1">
                            owner {segment.owner || "unknown"}
                          </span>
                          <span className="rounded-full border border-zinc-800 px-2 py-1">
                            {formatRelativeDate(segment.updated_at)}
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
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2 text-sm font-medium text-zinc-100">
                  <Filter size={15} className="text-zinc-500" />
                  Segment details
                </div>
                <div className="flex items-center gap-3">
                  <FeedbackButton
                    adapter={adapter}
                    surface="segments.detail"
                    segmentRef={selectedSegmentId}
                    context={{ selected_segment_id: selectedSegmentId }}
                    buttonLabel="Share feedback"
                    buttonClassName="inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-600"
                  />
                  <button
                    type="button"
                    onClick={handleExport}
                    disabled={!detail || exporting}
                    className="inline-flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 transition disabled:cursor-not-allowed disabled:opacity-50 hover:border-zinc-700 hover:bg-zinc-900"
                  >
                    {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                    Export CSV
                  </button>
                </div>
              </div>
              {exportMessage ? (
                <p className="mt-3 text-sm text-zinc-500">{exportMessage}</p>
              ) : null}
            </div>

            <div className="min-h-0 max-h-full overflow-y-auto px-5 py-5">
              {detailLoading ? (
                <LoadingBlock label="Loading segment details..." />
              ) : detailError ? (
                <ErrorState title="Unable to load segment details" detail={detailError} />
              ) : detail ? (
                <div className="space-y-5">
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-950 p-5">
                    <h2 className="text-lg font-medium text-zinc-100">
                      {detail.segment.segment_name}
                    </h2>
                    <p className="mt-2 text-sm text-zinc-500">
                      {detail.segment.description || "No description saved yet."}
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Tag>{detail.segment.segment_key}</Tag>
                      <Tag>{detail.segment.total_count} members</Tag>
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <StatCard
                      label="Profiles"
                      value={String(detail.stats.profile_count ?? detail.segment.total_count)}
                    />
                    <StatCard
                      label="Email coverage"
                      value={`${detail.stats.contact_coverage?.email_coverage_percent ?? 0}%`}
                    />
                    <StatCard
                      label="Phone coverage"
                      value={`${detail.stats.contact_coverage?.phone_coverage_percent ?? 0}%`}
                    />
                    <StatCard
                      label="Top city"
                      value={detail.stats.top_cities?.[0]?.city || "Unknown"}
                    />
                  </div>

                  <div className="rounded-2xl border border-zinc-800 bg-zinc-950 p-5">
                    <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-zinc-500">
                      Member preview
                    </p>
                    <div className="mt-4 space-y-3">
                      {detail.segment.rows.slice(0, 12).map((row) => (
                        <div
                          key={row.id}
                          className="rounded-xl border border-zinc-800 bg-[#050505] px-4 py-3"
                        >
                          <p className="text-sm font-medium text-zinc-100">
                            {row.company_name || row.kbo_number || row.id}
                          </p>
                          <p className="mt-1 text-xs text-zinc-500">
                            {row.city || "Unknown city"} · {row.status || "Unknown status"}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="Select a segment"
                  detail="Choose a segment from the list to view its details."
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function CreateSegmentForm({
  value,
  pending,
  error,
  onChange,
  onSubmit,
}: {
  value: CreateSegmentInput;
  pending: boolean;
  error: string | null;
  onChange: <Key extends keyof CreateSegmentInput>(
    key: Key,
    value: CreateSegmentInput[Key],
  ) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <form
      onSubmit={onSubmit}
      className="mb-5 rounded-2xl border border-indigo-500/20 bg-indigo-500/5 p-5"
    >
      <div className="grid gap-3 md:grid-cols-2">
        <input
          required
          value={value.name}
          onChange={(event) => onChange("name", event.target.value)}
          placeholder="Segment name"
          className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
        />
        <input
          value={value.city}
          onChange={(event) => onChange("city", event.target.value)}
          placeholder="City"
          className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
        />
        <input
          value={value.keywords}
          onChange={(event) => onChange("keywords", event.target.value)}
          placeholder="Keywords / industry"
          className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
        />
        <select
          value={value.status}
          onChange={(event) => onChange("status", event.target.value)}
          className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
        >
          <option value="">Any status</option>
          <option value="AC">Active</option>
          <option value="ST">Stopped</option>
        </select>
        <input
          value={value.email_domain}
          onChange={(event) => onChange("email_domain", event.target.value)}
          placeholder="Email domain"
          className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
        />
        <input
          value={value.description}
          onChange={(event) => onChange("description", event.target.value)}
          placeholder="Description"
          className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
        />
      </div>

      <div className="mt-4 flex flex-wrap gap-4 text-sm text-zinc-300">
        <label className="inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={Boolean(value.has_email)}
            onChange={(event) => onChange("has_email", event.target.checked)}
          />
          Require email
        </label>
        <label className="inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={Boolean(value.has_phone)}
            onChange={(event) => onChange("has_phone", event.target.checked)}
          />
          Require phone
        </label>
      </div>

      {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}

      <div className="mt-5 flex justify-end">
        <button
          type="submit"
          disabled={pending}
          className="inline-flex items-center gap-2 rounded-xl bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
        >
          {pending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
          Create canonical segment
        </button>
      </div>
    </form>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-zinc-800 px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.16em] text-zinc-400">
      {children}
    </span>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-[#050505] px-4 py-4">
      <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-zinc-500">{label}</p>
      <p className="mt-2 text-lg font-medium text-zinc-100">{value}</p>
    </div>
  );
}

function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="flex min-h-[260px] flex-col items-center justify-center gap-3 text-zinc-500">
      <Loader2 size={22} className="animate-spin" />
      <p className="text-sm">{label}</p>
    </div>
  );
}
