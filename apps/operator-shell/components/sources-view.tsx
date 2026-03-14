import { useState } from "react";
import { Database, RefreshCw, CheckCircle2, AlertCircle, Plus, Loader2, AlertTriangle } from "lucide-react";
import { StateSwitcher, type ViewState } from "./state-switcher";

export function SourcesView() {
  const [viewState, setViewState] = useState<ViewState>("success");

  const sources = [
    { id: "exact", name: "Exact Online", type: "ERP / Finance", status: "connected", lastSync: "2m ago", records: "12,450" },
    { id: "teamleader", name: "Teamleader", type: "CRM", status: "connected", lastSync: "5m ago", records: "8,201" },
    { id: "autotask", name: "Autotask", type: "PSA / Support", status: "connected", lastSync: "1m ago", records: "45,102" },
    { id: "resend", name: "Resend", type: "Email Delivery", status: "connected", lastSync: "1h ago", records: "142,000" },
    { id: "tracardi", name: "Tracardi", type: "CDP Activation", status: "connected", lastSync: "12m ago", records: "10,400" },
    { id: "hubspot", name: "HubSpot", type: "Marketing", status: "disconnected", lastSync: "-", records: "-" },
  ];

  return (
    <div className="flex-1 flex flex-col bg-[#050505] overflow-hidden">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-8 justify-between shrink-0 bg-zinc-950/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-[6px] bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
            <Database size={16} className="text-emerald-400" />
          </div>
          <h1 className="text-lg font-medium text-zinc-100">Data Sources</h1>
        </div>
        <div className="flex items-center gap-4">
          <StateSwitcher currentState={viewState} onStateChange={setViewState} />
          <button className="flex items-center gap-2 bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
            <Plus size={16} />
            Add Source
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-6xl mx-auto flex flex-col gap-8">
          
          {viewState === "loading" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500">
              <Loader2 size={24} className="animate-spin mb-4 text-emerald-500" />
              <p className="text-sm font-medium">Loading data sources...</p>
            </div>
          )}

          {viewState === "empty" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500 border border-dashed border-zinc-800 rounded-[8px] bg-zinc-900/20">
              <Database size={32} className="mb-4 text-zinc-600" />
              <p className="text-sm font-medium text-zinc-300">No sources configured</p>
              <p className="text-xs mt-1 max-w-sm text-center">Connect your first data source to start building segments and pipelines.</p>
              <button className="mt-6 flex items-center gap-2 bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
                <Plus size={16} />
                Add Source
              </button>
            </div>
          )}

          {viewState === "error" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500 border border-zinc-800 rounded-[8px] bg-rose-500/5">
              <AlertTriangle size={32} className="mb-4 text-rose-500" />
              <p className="text-sm font-medium text-rose-400">Failed to load sources</p>
              <p className="text-xs mt-1 max-w-sm text-center text-zinc-400">There was an error connecting to the integration service. Please try again later.</p>
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
                    <p className="text-amber-400 font-medium">Sync issues detected</p>
                    <p className="text-amber-500/70 mt-0.5">Some sources are experiencing delays. Data from Exact Online may be up to 2 hours old.</p>
                  </div>
                </div>
              )}
              
              <div className="grid grid-cols-3 gap-6">
                {sources.map(source => (
                  <div key={source.id} className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-5 flex flex-col gap-4 hover:border-zinc-700 transition-colors">
                    <div className="flex items-start justify-between">
                      <div className="flex flex-col gap-1">
                        <h3 className="text-base font-medium text-zinc-200">{source.name}</h3>
                        <span className="text-xs font-mono text-zinc-500 uppercase tracking-wider">{source.type}</span>
                      </div>
                      <div className={`flex items-center gap-1.5 px-2 py-1 rounded-[4px] border ${
                        source.status === 'connected' 
                          ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                          : 'bg-zinc-800 border-zinc-700 text-zinc-400'
                      }`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${source.status === 'connected' ? 'bg-emerald-500' : 'bg-zinc-500'}`} />
                        <span className="text-[10px] font-mono uppercase tracking-wider">{source.status}</span>
                      </div>
                    </div>

                    <div className="flex flex-col gap-3 mt-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-zinc-500">Last Sync</span>
                        <span className="font-mono text-zinc-300 flex items-center gap-1.5">
                          {source.status === 'connected' && <RefreshCw size={12} className="text-zinc-500" />}
                          {source.lastSync}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-zinc-500">Records Synced</span>
                        <span className="font-mono text-zinc-300">{source.records}</span>
                      </div>
                    </div>

                    <div className="mt-2 pt-4 border-t border-zinc-800 flex items-center justify-between">
                      {source.status === 'connected' ? (
                        <span className="text-xs text-emerald-500/80 flex items-center gap-1.5">
                          <CheckCircle2 size={14} /> Healthy
                        </span>
                      ) : (
                        <span className="text-xs text-zinc-500 flex items-center gap-1.5">
                          <AlertCircle size={14} /> Not Configured
                        </span>
                      )}
                      <button className="text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors">
                        Configure
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

        </div>
      </div>
    </div>
  );
}
