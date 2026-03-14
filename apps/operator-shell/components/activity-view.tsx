import { useState } from "react";
import { Activity, Search, Filter, AlertTriangle, CheckCircle2, Info, XCircle, Loader2 } from "lucide-react";
import { StateSwitcher, type ViewState } from "./state-switcher";

export function ActivityView() {
  const [viewState, setViewState] = useState<ViewState>("success");

  const activities = [
    { id: 1, type: "sync", status: "partial", title: "Segment Sync: Tech Enterprise Active", description: "Synced to Tracardi. 12 succeeded, 2 failed (missing email).", user: "System", time: "10 mins ago" },
    { id: 2, type: "prompt", status: "success", title: "Prompt Run: Churn Risk Analysis", description: "Generated 3 new segments based on recent Autotask tickets.", user: "Lennert V.", time: "1 hour ago" },
    { id: 3, type: "send", status: "success", title: "Resend Broadcast: Q3 Update", description: "Sent to 28 contacts in 'Recent Onboarding' segment.", user: "Sarah P.", time: "3 hours ago" },
    { id: 4, type: "exclusion", status: "warning", title: "Exclusion Rule Applied", description: "Excluded 5 companies from 'Upsell Candidates' due to active support escalations.", user: "System", time: "5 hours ago" },
    { id: 5, type: "sync", status: "error", title: "Segment Sync: Churn Risk - High Value", description: "Failed to sync to Tracardi. API rate limit exceeded.", user: "System", time: "1 day ago" },
    { id: 6, type: "prompt", status: "success", title: "Prompt Run: Identify Upsell", description: "Queried Exact Online for customers with >€10k revenue.", user: "Lennert V.", time: "1 day ago" },
  ];

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "success": return <CheckCircle2 size={16} className="text-emerald-500" />;
      case "warning": return <AlertTriangle size={16} className="text-amber-500" />;
      case "partial": return <Info size={16} className="text-indigo-400" />;
      case "error": return <XCircle size={16} className="text-rose-500" />;
      default: return <Info size={16} className="text-zinc-500" />;
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-[#050505] overflow-hidden">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-8 justify-between shrink-0 bg-zinc-950/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-[6px] bg-zinc-800 border border-zinc-700 flex items-center justify-center">
            <Activity size={16} className="text-zinc-300" />
          </div>
          <h1 className="text-lg font-medium text-zinc-100">Activity & Audit</h1>
        </div>
        <div className="flex items-center gap-4">
          <StateSwitcher currentState={viewState} onStateChange={setViewState} />
          <button className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-[6px] text-sm text-zinc-400 hover:text-zinc-200 transition-colors">
            <Filter size={14} />
            Filter Events
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-5xl mx-auto flex flex-col gap-6">
          
          <div className="flex items-center justify-between">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={14} />
              <input 
                type="text" 
                placeholder="Search activity logs..." 
                className="bg-zinc-900 border border-zinc-800 rounded-[6px] py-1.5 pl-9 pr-4 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-600 w-80"
              />
            </div>
            <div className="text-sm text-zinc-500 font-mono">
              Showing last 30 days
            </div>
          </div>

          {viewState === "loading" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500">
              <Loader2 size={24} className="animate-spin mb-4 text-zinc-500" />
              <p className="text-sm font-medium">Loading activity logs...</p>
            </div>
          )}

          {viewState === "empty" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500 border border-dashed border-zinc-800 rounded-[8px] bg-zinc-900/20">
              <Activity size={32} className="mb-4 text-zinc-600" />
              <p className="text-sm font-medium text-zinc-300">No recent activity</p>
              <p className="text-xs mt-1 max-w-sm text-center">There are no audit logs or activities recorded in the selected timeframe.</p>
            </div>
          )}

          {viewState === "error" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500 border border-zinc-800 rounded-[8px] bg-rose-500/5">
              <AlertTriangle size={32} className="mb-4 text-rose-500" />
              <p className="text-sm font-medium text-rose-400">Failed to load activity</p>
              <p className="text-xs mt-1 max-w-sm text-center text-zinc-400">There was an error connecting to the audit log service. Please try again later.</p>
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
                    <p className="text-amber-400 font-medium">Partial logs loaded</p>
                    <p className="text-amber-500/70 mt-0.5">Some older audit logs could not be retrieved from cold storage. Showing recent activity only.</p>
                  </div>
                </div>
              )}
              
              {/* Activity List */}
              <div className="border border-zinc-800 rounded-[8px] bg-[#0a0a0a] overflow-hidden">
                <div className="flex flex-col divide-y divide-zinc-800/50">
                  {activities.map((activity) => (
                    <div key={activity.id} className="flex items-start gap-4 p-4 hover:bg-zinc-900/30 transition-colors group">
                      <div className="mt-1">
                        {getStatusIcon(activity.status)}
                      </div>
                      <div className="flex-1 flex flex-col gap-1">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-zinc-200">{activity.title}</span>
                          <span className="text-xs font-mono text-zinc-500">{activity.time}</span>
                        </div>
                        <p className="text-sm text-zinc-400">{activity.description}</p>
                        <div className="flex items-center gap-3 mt-2">
                          <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 bg-zinc-900 px-2 py-0.5 rounded-[4px] border border-zinc-800">
                            {activity.type}
                          </span>
                          <span className="text-xs text-zinc-500">
                            Initiated by <span className="text-zinc-300">{activity.user}</span>
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

        </div>
      </div>
    </div>
  );
}
