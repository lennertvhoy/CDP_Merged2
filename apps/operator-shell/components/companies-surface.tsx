"use client";

import { useDeferredValue, useEffect, useState } from "react";
import {
  ArrowUpRight,
  Building2,
  Loader2,
  Search,
  Ticket,
  Users,
} from "lucide-react";

import {
  EmptyState,
  ErrorState,
  SectionHeader,
  SurfacePill,
} from "@/components/shell-primitives";
import { FeedbackButton } from "@/components/feedback-button";
import { formatCurrency, formatRelativeDate } from "@/lib/formatters";
import type { OperatorShellAdapter } from "@/lib/adapters/operator-shell";
import type {
  CompanyDetailPayload,
  CompanyListPayload,
  SurfaceDescriptor,
} from "@/lib/types/operator";

export function CompaniesSurface({
  adapter,
  surface,
}: {
  adapter: OperatorShellAdapter;
  surface: SurfaceDescriptor;
}) {
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [status, setStatus] = useState("");
  const deferredQuery = useDeferredValue(query);
  const deferredCity = useDeferredValue(city);
  const deferredStatus = useDeferredValue(status);
  const [payload, setPayload] = useState<CompanyListPayload | null>(null);
  const [detail, setDetail] = useState<CompanyDetailPayload | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    void adapter
      .getCompanies({
        query: deferredQuery,
        city: deferredCity,
        status: deferredStatus,
      })
      .then((result) => {
        if (!active) {
          return;
        }
        setPayload(result);
        setSelectedCompany((current) => current ?? result.companies[0]?.id ?? null);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Failed to load companies.");
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
  }, [adapter, deferredCity, deferredQuery, deferredStatus]);

  useEffect(() => {
    if (!selectedCompany) {
      setDetail(null);
      return;
    }

    let active = true;
    setDetailLoading(true);
    setDetailError(null);

    void adapter
      .getCompany(selectedCompany)
      .then((result) => {
        if (active) {
          setDetail(result);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setDetailError(reason instanceof Error ? reason.message : "Failed to load company detail.");
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
  }, [adapter, selectedCompany]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-[#050505]">
      <SectionHeader
        title="Companies"
        detail="Search companies and open the detail view."
        actions={
          <div className="flex items-center gap-3">
            <FeedbackButton
              adapter={adapter}
              surface="companies"
              companyRef={selectedCompany}
              context={{ query, city, status }}
              buttonLabel="Report company issue"
            />
            <SurfacePill mode={surface.mode} />
          </div>
        }
      />

      <div className="flex-1 overflow-hidden px-8 py-8">
        <div className="grid h-full gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
          <div className="flex min-h-0 flex-col rounded-2xl border border-zinc-800 bg-[#0a0a0a]">
            <div className="grid gap-3 border-b border-zinc-800 px-5 py-4 md:grid-cols-3">
              <label className="relative md:col-span-2">
                <Search
                  size={14}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600"
                />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search by company name or KBO..."
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 py-2.5 pl-9 pr-4 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
                />
              </label>
              <div className="grid gap-3 md:grid-cols-2">
                <input
                  value={city}
                  onChange={(event) => setCity(event.target.value)}
                  placeholder="City"
                  className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
                />
                <select
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                  className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
                >
                  <option value="">All statuses</option>
                  <option value="AC">Active</option>
                  <option value="ST">Stopped</option>
                </select>
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
              {loading ? (
                <LoadingBlock label="Loading company summaries..." />
              ) : error ? (
                <ErrorState title="Company lookup failed" detail={error} />
              ) : payload && payload.companies.length === 0 ? (
                <EmptyState
                  title="No companies matched these filters"
                  detail="Try changing the search or filters."
                />
              ) : (
                <div className="space-y-3">
                  <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-zinc-500">
                    {payload?.total ?? 0} companies
                  </div>
                  {payload?.companies.map((company) => {
                    const selected = selectedCompany === company.id;
                    return (
                      <button
                        key={company.id}
                        type="button"
                        onClick={() => setSelectedCompany(company.id)}
                        className={`w-full rounded-2xl border p-4 text-left transition ${
                          selected
                            ? "border-emerald-500/30 bg-emerald-500/5"
                            : "border-zinc-800 bg-zinc-950 hover:border-zinc-700"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="space-y-1">
                            <h2 className="text-sm font-medium text-zinc-100">{company.name}</h2>
                            <p className="text-xs text-zinc-500">
                              {company.kbo_number || company.company_uid} · {company.city || "Unknown city"}
                            </p>
                          </div>
                          <span className="rounded-full border border-zinc-800 px-2 py-1 text-[10px] font-mono uppercase tracking-[0.16em] text-zinc-400">
                            {company.status || "Unknown"}
                          </span>
                        </div>

                        <div className="mt-3 grid gap-3 md:grid-cols-3">
                          <Metric label="Exact revenue" value={formatCurrency(company.exact_revenue_ytd)} />
                          <Metric
                            label="Open tickets"
                            value={company.open_tickets === null ? "Unavailable" : String(company.open_tickets)}
                          />
                          <Metric
                            label="Account manager"
                            value={company.account_manager || "Not linked"}
                          />
                        </div>

                        <div className="mt-4 flex flex-wrap gap-2">
                          {company.linked_systems.map((system) => (
                            <span
                              key={system}
                              className="rounded-full border border-zinc-800 px-2 py-1 text-[10px] font-mono uppercase tracking-[0.16em] text-zinc-400"
                            >
                              {system}
                            </span>
                          ))}
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
                  <Building2 size={15} className="text-zinc-500" />
                  Company details
                </div>
                <FeedbackButton
                  adapter={adapter}
                  surface="companies.detail"
                  companyRef={selectedCompany}
                  context={{ selected_company: selectedCompany }}
                  buttonLabel="Share feedback"
                  buttonClassName="inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-600"
                />
              </div>
            </div>

            <div className="min-h-0 max-h-full overflow-y-auto px-5 py-5">
              {detailLoading ? (
                <LoadingBlock label="Loading company details..." />
              ) : detailError ? (
                <ErrorState title="Unable to load company details" detail={detailError} />
              ) : detail ? (
                <div className="space-y-5">
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-950 p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-zinc-500">
                          Company profile
                        </p>
                        <h2 className="mt-2 text-lg font-medium text-zinc-100">
                          {detail.company.name}
                        </h2>
                        <p className="mt-1 text-sm text-zinc-500">
                          {detail.company.kbo_number || detail.company.company_uid} · {detail.company.city || "Unknown city"}
                        </p>
                      </div>
                      <span className="rounded-full border border-zinc-800 px-2 py-1 text-[10px] font-mono uppercase tracking-[0.16em] text-zinc-400">
                        {detail.company.identity_link_status}
                      </span>
                    </div>

                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      <Metric label="Legal form" value={detail.company.legal_form || "Unknown"} />
                      <Metric label="Industry" value={detail.company.nace_description || "Unknown"} />
                      <Metric label="Employees" value={String(detail.company.employee_count ?? "Unknown")} />
                      <Metric label="Last refreshed" value={formatRelativeDate(detail.company.last_updated_at)} />
                    </div>

                    {detail.company.website_url ? (
                      <a
                        href={detail.company.website_url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-4 inline-flex items-center gap-2 text-sm text-zinc-300 transition hover:text-white"
                      >
                        Open website <ArrowUpRight size={14} />
                      </a>
                    ) : null}
                  </div>

                  <div className="grid gap-4 md:grid-cols-3">
                    <SourceCard title="Teamleader" payload={detail.sources.teamleader} />
                    <SourceCard title="Exact" payload={detail.sources.exact} />
                    <SourceCard title="Autotask" payload={detail.sources.autotask} />
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <FactCard
                      title="Financials"
                      icon={<Users size={14} className="text-zinc-500" />}
                      rows={[
                        ["Revenue YTD", formatCurrency(numberOrNull(detail.financials.revenue_ytd))],
                        ["Outstanding", formatCurrency(numberOrNull(detail.financials.outstanding_amount))],
                        ["Overdue", formatCurrency(numberOrNull(detail.financials.overdue_amount))],
                      ]}
                    />
                    <FactCard
                      title="Pipeline"
                      icon={<Ticket size={14} className="text-zinc-500" />}
                      rows={[
                        ["Open deals", String(detail.pipeline.open_deals_count ?? "0")],
                        ["Open value", formatCurrency(numberOrNull(detail.pipeline.open_deals_value))],
                        ["Won YTD", formatCurrency(numberOrNull(detail.pipeline.won_value_ytd))],
                      ]}
                    />
                  </div>

                  <div className="rounded-2xl border border-zinc-800 bg-zinc-950 p-5">
                    <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-zinc-500">
                      Activity timeline
                    </p>
                    <div className="mt-4 space-y-3">
                      {detail.activity.length === 0 ? (
                        <p className="text-sm text-zinc-500">
                          No activity rows were returned for this company.
                        </p>
                      ) : (
                        detail.activity.slice(0, 8).map((event) => (
                          <article
                            key={`${event.activity_type}-${event.activity_date}`}
                            className="rounded-xl border border-zinc-800 bg-[#050505] p-3"
                          >
                            <div className="flex items-start justify-between gap-4">
                              <div>
                                <p className="text-sm font-medium text-zinc-100">
                                  {event.activity_description}
                                </p>
                                <p className="mt-1 text-[10px] font-mono uppercase tracking-[0.16em] text-zinc-500">
                                  {event.source_system} · {event.activity_type}
                                </p>
                              </div>
                              <span className="text-[11px] font-mono text-zinc-500">
                                {formatRelativeDate(event.activity_date)}
                              </span>
                            </div>
                          </article>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="Select a company"
                  detail="Choose a company from the list to view more details."
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-[#050505] px-3 py-3">
      <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-zinc-500">{label}</p>
      <p className="mt-2 text-sm text-zinc-100">{value}</p>
    </div>
  );
}

function SourceCard({
  title,
  payload,
}: {
  title: string;
  payload: Record<string, unknown>;
}) {
  const entries = Object.entries(payload).filter(([, value]) => value !== null && value !== false);
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950 p-4">
      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-zinc-500">{title}</p>
      <div className="mt-4 space-y-2">
        {entries.length === 0 ? (
          <p className="text-sm text-zinc-500">No linked data.</p>
        ) : (
          entries.slice(0, 6).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between gap-4 text-sm">
              <span className="text-zinc-500">{key.replaceAll("_", " ")}</span>
              <span className="text-right text-zinc-200">{String(value)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function FactCard({
  title,
  icon,
  rows,
}: {
  title: string;
  icon: React.ReactNode;
  rows: Array<[string, string]>;
}) {
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950 p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-zinc-100">
        {icon}
        {title}
      </div>
      <div className="mt-4 space-y-3">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-4 text-sm">
            <span className="text-zinc-500">{label}</span>
            <span className="text-zinc-100">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="flex min-h-[260px] flex-col items-center justify-center gap-3 text-zinc-500">
      <Loader2 size={22} className="animate-spin" />
      <p className="text-sm">{label}</p>
    </div>
  );
}
