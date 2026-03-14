import { useState } from "react";
import { Filter, MoreHorizontal, Users, Play, Clock, RefreshCw, Copy, Archive, AlertTriangle, Loader2 } from "lucide-react";
import { StateSwitcher, type ViewState } from "./state-switcher";

export function SegmentsView() {
  const [viewState, setViewState] = useState<ViewState>("success");

  const segments = [
    { id: "seg_1", name: "Tech Enterprise Active", description: "Active tech clients with Exact revenue > €0 and open Autotask tickets.", size: 14, lastRefreshed: "2m ago", status: "active" },
    { id: "seg_2", name: "Churn Risk - High Value", description: "Customers with > €50k revenue and no engagement in 90 days.", size: 3, lastRefreshed: "1h ago", status: "active" },
    { id: "seg_3", name: "Recent Onboarding", description: "New Teamleader deals closed in the last 30 days.", size: 28, lastRefreshed: "4h ago", status: "active" },
    { id: "seg_4", name: "Upsell Candidates", description: "Healthy SLA, > €10k revenue, no active upsell deal.", size: 42, lastRefreshed: "1d ago", status: "paused" },
  ];

  return (
    <div className="flex-1 flex flex-col bg-[#050505] overflow-hidden">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-8 justify-between shrink-0 bg-zinc-950/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-[6px] bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
            <Users size={16} className="text-indigo-400" />
          </div>
          <h1 className="text-lg font-medium text-zinc-100">Saved Segments</h1>
        </div>
        <div className="flex items-center gap-4">
          <StateSwitcher currentState={viewState} onStateChange={setViewState} />
          <button className="bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
            Create Segment
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-6xl mx-auto flex flex-col gap-6">
          
          {/* Filters */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="relative">
                <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={14} />
                <input 
                  type="text" 
                  placeholder="Search segments..." 
                  className="bg-zinc-900 border border-zinc-800 rounded-[6px] py-1.5 pl-9 pr-4 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-600 w-64"
                />
              </div>
              <button className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-[6px] text-sm text-zinc-400 hover:text-zinc-200 transition-colors">
                <Filter size={14} />
                Filter
              </button>
            </div>
            <div className="text-sm text-zinc-500 font-mono">
              {viewState === "success" || viewState === "partial" ? segments.length : 0} segments total
            </div>
          </div>

          {viewState === "loading" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500">
              <Loader2 size={24} className="animate-spin mb-4 text-indigo-500" />
              <p className="text-sm font-medium">Loading segments...</p>
            </div>
          )}

          {viewState === "empty" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500 border border-dashed border-zinc-800 rounded-[8px] bg-zinc-900/20">
              <Users size={32} className="mb-4 text-zinc-600" />
              <p className="text-sm font-medium text-zinc-300">No segments found</p>
              <p className="text-xs mt-1 max-w-sm text-center">You haven't created any segments yet. Use the operator to build your first audience.</p>
              <button className="mt-6 bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
                Create Segment
              </button>
            </div>
          )}

          {viewState === "error" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500 border border-zinc-800 rounded-[8px] bg-rose-500/5">
              <AlertTriangle size={32} className="mb-4 text-rose-500" />
              <p className="text-sm font-medium text-rose-400">Failed to load segments</p>
              <p className="text-xs mt-1 max-w-sm text-center text-zinc-400">There was an error connecting to the segment database. Please try again later.</p>
              <button className="mt-6 bg-zinc-900 border border-zinc-700 hover:bg-zinc-800 text-zinc-300 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
                Retry Connection
              </button>
            </div>
          )}

          {(viewState === "success" || viewState === "partial") && (
            <>
              {viewState === "partial" && (
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-[6px] p-3 flex items-start gap-3 text-sm">
                  <AlertTriangle size={16} className="text-amber-500 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-amber-400 font-medium">Partial data loaded</p>
                    <p className="text-amber-500/70 mt-0.5">Some segments could not be retrieved from the cache. Showing 4 of 12 segments.</p>
                  </div>
                </div>
              )}
              
              {/* Table */}
              <div className="border border-zinc-800 rounded-[8px] bg-[#0a0a0a] overflow-hidden">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-zinc-800 bg-zinc-900/50">
                      <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Segment Name</th>
                      <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Size</th>
                      <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Last Refreshed</th>
                      <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Status</th>
                      <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800">
                    {segments.map((segment) => (
                      <tr key={segment.id} className="hover:bg-zinc-900/30 transition-colors group">
                        <td className="px-6 py-4">
                          <div className="flex flex-col gap-1">
                            <span className="text-sm font-medium text-zinc-200">{segment.name}</span>
                            <span className="text-xs text-zinc-500 truncate max-w-md">{segment.description}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-sm font-mono text-zinc-300">{segment.size}</span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-1.5 text-xs font-mono text-zinc-500">
                            <Clock size={12} />
                            {segment.lastRefreshed}
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-[4px] border ${
                            segment.status === 'active' 
                              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                              : 'bg-zinc-800 border-zinc-700 text-zinc-400'
                          }`}>
                            <div className={`w-1.5 h-1.5 rounded-full ${segment.status === 'active' ? 'bg-emerald-500' : 'bg-zinc-500'}`} />
                            <span className="text-[10px] font-mono uppercase tracking-wider">{segment.status}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-[4px] transition-colors">
                              <Play size={12} />
                              Open
                            </button>
                            <button className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-[4px] transition-colors">
                              <RefreshCw size={12} />
                              Refresh
                            </button>
                            <button className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-[4px] transition-colors">
                              <Copy size={12} />
                              Duplicate
                            </button>
                            <button className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-[4px] transition-colors">
                              <Archive size={12} />
                              Archive
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

        </div>
      </div>
    </div>
  );
}

function SearchIcon(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}
