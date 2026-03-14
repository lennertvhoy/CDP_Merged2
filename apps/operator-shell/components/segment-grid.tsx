import { useState } from "react";
import { Filter, Download, Send, Database, AlertCircle, Mail, Loader2, AlertTriangle } from "lucide-react";
import { StateSwitcher, type ViewState } from "./state-switcher";

export function SegmentGrid({ onRowClick, activeRow }: { onRowClick?: (id: string) => void, activeRow?: string | null }) {
  const [viewState, setViewState] = useState<ViewState>("success");

  return (
    <div className="flex flex-col gap-6">
      {/* Header Section */}
      <div className="flex items-start justify-between pb-6 border-b border-zinc-800">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-medium text-zinc-100 tracking-tight">Active Tech Enterprises (Revenue & Tickets)</h1>
            <div className="px-2 py-0.5 rounded-[4px] bg-zinc-800 border border-zinc-700 text-zinc-300 text-[10px] font-mono uppercase tracking-wider">
              {viewState === "success" || viewState === "partial" ? "14 Results" : "0 Results"}
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1.5 text-zinc-400">
              <Filter size={14} />
              <span>Segment Builder</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <StateSwitcher currentState={viewState} onStateChange={setViewState} />
          <div className="flex items-center gap-2">
            <button 
              className="flex items-center gap-2 text-xs font-mono bg-zinc-900 border border-zinc-700 hover:bg-zinc-800 text-zinc-300 px-3 py-1.5 rounded-[4px] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={viewState !== "success" && viewState !== "partial"}
            >
              <Download size={14} />
              Export CSV
            </button>
            <button 
              className="flex items-center gap-2 text-xs font-mono bg-indigo-500/10 border border-indigo-500/20 hover:bg-indigo-500/20 text-indigo-400 px-3 py-1.5 rounded-[4px] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={viewState !== "success" && viewState !== "partial"}
            >
              <Send size={14} />
              Sync to Tracardi
            </button>
          </div>
        </div>
      </div>

      {/* Audit & Logic Block (Explainability) */}
      <div className="bg-[#0a0a0a] border border-zinc-800 rounded-[6px] p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-medium text-zinc-300 uppercase tracking-wider">
            <Database size={14} className="text-zinc-500" />
            PostgreSQL Query Logic
          </div>
          <div className="text-[10px] font-mono text-zinc-500">
            Execution time: {viewState === "loading" ? "..." : "124ms"}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <LogicChip field="lifecycle_stage" operator="=" value="'Customer'" source="Teamleader" />
          <LogicChip field="industry" operator="=" value="'Technology'" source="Teamleader" />
          <LogicChip field="ytd_revenue" operator=">" value="0" source="Exact Online" />
          <LogicChip field="open_tickets" operator=">=" value="1" source="Autotask" />
        </div>
      </div>

      {viewState === "loading" && (
        <div className="border border-zinc-800 rounded-[6px] overflow-hidden bg-[#0a0a0a] flex flex-col items-center justify-center py-24 text-zinc-500">
          <Loader2 size={24} className="animate-spin mb-4 text-indigo-500" />
          <p className="text-sm font-medium">Executing query across sources...</p>
        </div>
      )}

      {viewState === "empty" && (
        <div className="border border-dashed border-zinc-800 rounded-[6px] bg-zinc-900/20 flex flex-col items-center justify-center py-24 text-zinc-500">
          <Filter size={32} className="mb-4 text-zinc-600" />
          <p className="text-sm font-medium text-zinc-300">No companies match this segment</p>
          <p className="text-xs mt-1 max-w-sm text-center">Try adjusting your query logic or removing some filters to see results.</p>
        </div>
      )}

      {viewState === "error" && (
        <div className="border border-zinc-800 rounded-[6px] bg-rose-500/5 flex flex-col items-center justify-center py-24 text-zinc-500">
          <AlertTriangle size={32} className="mb-4 text-rose-500" />
          <p className="text-sm font-medium text-rose-400">Query execution failed</p>
          <p className="text-xs mt-1 max-w-sm text-center text-zinc-400">There was an error connecting to the Exact Online data source. Please check your connection.</p>
          <button className="mt-6 bg-zinc-900 border border-zinc-700 hover:bg-zinc-800 text-zinc-300 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
            Retry Query
          </button>
        </div>
      )}

      {(viewState === "success" || viewState === "partial") && (
        <div className="flex flex-col gap-4">
          {viewState === "partial" && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-[6px] p-3 flex items-start gap-3 text-sm">
              <AlertTriangle size={16} className="text-amber-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-amber-400 font-medium">Incomplete results</p>
                <p className="text-amber-500/70 mt-0.5">The Exact Online connection timed out. Revenue data is currently unavailable for some companies.</p>
              </div>
            </div>
          )}

          {/* Data Grid */}
          <div className="border border-zinc-800 rounded-[6px] overflow-hidden bg-[#0a0a0a]">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-zinc-900/50 border-b border-zinc-800 text-xs font-mono text-zinc-500 uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3 font-medium">Company Name</th>
                    <th className="px-4 py-3 font-medium">VAT Number</th>
                    <th className="px-4 py-3 font-medium">Account Manager</th>
                    <th className="px-4 py-3 font-medium text-right">YTD Revenue (Exact)</th>
                    <th className="px-4 py-3 font-medium text-center">Open Tickets (Autotask)</th>
                    <th className="px-4 py-3 font-medium text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  <DataRow 
                    name="TechCorp Belgium NV" 
                    vat="BE0412345678" 
                    manager="Sarah Peeters" 
                    revenue="€142,500.00" 
                    tickets="2" 
                    status="Active" 
                    onClick={() => onRowClick?.("BE0412345678")}
                    isActive={activeRow === "BE0412345678"}
                  />
                  <DataRow 
                    name="DataFlow Systems" 
                    vat="BE0876543210" 
                    manager="Tom De Smet" 
                    revenue="€84,200.00" 
                    tickets="1" 
                    status="Active" 
                    onClick={() => onRowClick?.("BE0876543210")}
                    isActive={activeRow === "BE0876543210"}
                  />
                  <DataRow 
                    name="CloudNative BV" 
                    vat="BE0998877665" 
                    manager="Sarah Peeters" 
                    revenue="€11,150.00" 
                    tickets="5" 
                    status="Warning" 
                    onClick={() => onRowClick?.("BE0998877665")}
                    isActive={activeRow === "BE0998877665"}
                  />
                  <DataRow 
                    name="CyberSec Partners" 
                    vat="BE0112233445" 
                    manager="Jan Mertens" 
                    revenue="Unavailable" 
                    tickets="1" 
                    status="Active" 
                    isUnavailable
                    onClick={() => onRowClick?.("BE0112233445")}
                    isActive={activeRow === "BE0112233445"}
                  />
                  <DataRow 
                    name="AI Solutions Group" 
                    vat="BE0554433221" 
                    manager="Tom De Smet" 
                    revenue="€108,900.00" 
                    tickets="3" 
                    status="Active" 
                    onClick={() => onRowClick?.("BE0554433221")}
                    isActive={activeRow === "BE0554433221"}
                  />
                </tbody>
              </table>
            </div>
            <div className="px-4 py-3 bg-zinc-950/50 border-t border-zinc-800 text-[10px] font-mono text-zinc-500 flex justify-between items-center">
              <span>Showing 1-5 of 14 results</span>
              <span>Data retrieved directly from PostgreSQL Customer Intelligence Layer</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function LogicChip({ field, operator, value, source }: { field: string, operator: string, value: string, source: string }) {
  return (
    <div className="flex items-center gap-2 px-2.5 py-1.5 bg-zinc-950 border border-zinc-800 rounded-[4px] text-xs font-mono">
      <span className="text-indigo-400">{field}</span>
      <span className="text-zinc-500">{operator}</span>
      <span className="text-emerald-400">{value}</span>
      <span className="text-[9px] text-zinc-600 uppercase tracking-wider ml-2 border-l border-zinc-800 pl-2">[{source}]</span>
    </div>
  );
}

function DataRow({ 
  name, 
  vat, 
  manager, 
  revenue, 
  tickets, 
  status,
  isUnavailable = false,
  onClick,
  isActive
}: { 
  name: string, 
  vat: string, 
  manager: string, 
  revenue: string, 
  tickets: string, 
  status: string,
  isUnavailable?: boolean,
  onClick?: () => void,
  isActive?: boolean
}) {
  return (
    <tr 
      onClick={onClick} 
      className={`transition-colors group cursor-pointer relative ${isActive ? 'bg-indigo-500/10' : 'hover:bg-zinc-900/30'}`}
    >
      <td className="px-4 py-3 text-zinc-200 font-medium relative">
        {isActive && <div className="absolute left-0 top-0 bottom-0 w-1 bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.6)]" />}
        {name}
      </td>
      <td className="px-4 py-3 font-mono text-zinc-500 group-hover:text-zinc-400">{vat}</td>
      <td className="px-4 py-3 text-zinc-400">{manager}</td>
      <td className="px-4 py-3 text-right">
        {isUnavailable ? (
          <span className="text-[10px] font-mono bg-zinc-900 border border-zinc-800 text-zinc-500 px-1.5 py-0.5 rounded-[4px] cursor-help" title="Not provided by Exact SalesInvoice feed">
            Unavailable
          </span>
        ) : (
          <span className="font-mono text-zinc-300">{revenue}</span>
        )}
      </td>
      <td className="px-4 py-3 text-center">
        <span className={`font-mono px-2 py-0.5 rounded-[4px] ${parseInt(tickets) > 3 ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'text-zinc-400'}`}>
          {tickets}
        </span>
      </td>
      <td className="px-4 py-3 text-center">
        {status === 'Active' ? (
          <span className="inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-emerald-400 cursor-help" title="Healthy engagement and payment history">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            Active
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-amber-400 cursor-help" title="High open ticket volume or dropping engagement">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
            Warning
          </span>
        )}
      </td>
    </tr>
  );
}
