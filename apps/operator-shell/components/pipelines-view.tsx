import { useState } from "react";
import { GitBranch, Play, Pause, Settings, ArrowRight, Loader2, AlertTriangle } from "lucide-react";
import { StateSwitcher, type ViewState } from "./state-switcher";

export function PipelinesView() {
  const [viewState, setViewState] = useState<ViewState>("success");

  const pipelines = [
    { id: "pipe_1", name: "Daily CDP Sync", description: "Syncs 'Tech Enterprise Active' segment to Tracardi.", trigger: "Schedule: Daily at 00:00", action: "Tracardi: Update Profiles", status: "active", lastRun: "10h ago" },
    { id: "pipe_2", name: "Support Friction Pause", description: "Pauses marketing emails if open Autotask tickets > 0.", trigger: "Event: Ticket Created", action: "Resend: Remove from Audience", status: "active", lastRun: "2m ago" },
    { id: "pipe_3", name: "Churn Risk Alert", description: "Notifies Account Manager when engagement drops.", trigger: "Schedule: Weekly", action: "Slack: Send Alert", status: "paused", lastRun: "5d ago" },
  ];

  return (
    <div className="flex-1 flex flex-col bg-[#050505] overflow-hidden">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-8 justify-between shrink-0 bg-zinc-950/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-[6px] bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
            <GitBranch size={16} className="text-amber-400" />
          </div>
          <h1 className="text-lg font-medium text-zinc-100">Activation Pipelines</h1>
        </div>
        <div className="flex items-center gap-4">
          <StateSwitcher currentState={viewState} onStateChange={setViewState} />
          <button className="flex items-center gap-2 bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
            Create Pipeline
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-6xl mx-auto flex flex-col gap-6">
          
          {viewState === "loading" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500">
              <Loader2 size={24} className="animate-spin mb-4 text-amber-500" />
              <p className="text-sm font-medium">Loading pipelines...</p>
            </div>
          )}

          {viewState === "empty" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500 border border-dashed border-zinc-800 rounded-[8px] bg-zinc-900/20">
              <GitBranch size={32} className="mb-4 text-zinc-600" />
              <p className="text-sm font-medium text-zinc-300">No pipelines created</p>
              <p className="text-xs mt-1 max-w-sm text-center">Create your first pipeline to automate actions based on segment changes.</p>
              <button className="mt-6 flex items-center gap-2 bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
                Create Pipeline
              </button>
            </div>
          )}

          {viewState === "error" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500 border border-zinc-800 rounded-[8px] bg-rose-500/5">
              <AlertTriangle size={32} className="mb-4 text-rose-500" />
              <p className="text-sm font-medium text-rose-400">Failed to load pipelines</p>
              <p className="text-xs mt-1 max-w-sm text-center text-zinc-400">There was an error retrieving your pipeline configurations. Please try again.</p>
              <button className="mt-6 bg-zinc-900 border border-zinc-700 hover:bg-zinc-800 text-zinc-300 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
                Retry
              </button>
            </div>
          )}

          {(viewState === "success" || viewState === "partial") && (
            <div className="flex flex-col gap-4">
              {viewState === "partial" && (
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-[6px] p-3 flex items-start gap-3 text-sm mb-2">
                  <AlertTriangle size={16} className="text-amber-500 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-amber-400 font-medium">Pipeline execution delayed</p>
                    <p className="text-amber-500/70 mt-0.5">We are experiencing high load. Some scheduled pipelines may run a few minutes late.</p>
                  </div>
                </div>
              )}

              {pipelines.map(pipeline => (
                <div key={pipeline.id} className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex items-center justify-between hover:border-zinc-700 transition-colors group">
                  
                  <div className="flex flex-col gap-4 flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-base font-medium text-zinc-200">{pipeline.name}</h3>
                      <div className={`flex items-center gap-1.5 px-2 py-1 rounded-[4px] border ${
                        pipeline.status === 'active' 
                          ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                          : 'bg-zinc-800 border-zinc-700 text-zinc-400'
                      }`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${pipeline.status === 'active' ? 'bg-emerald-500' : 'bg-zinc-500'}`} />
                        <span className="text-[10px] font-mono uppercase tracking-wider">{pipeline.status}</span>
                      </div>
                    </div>
                    <p className="text-sm text-zinc-500 max-w-2xl">{pipeline.description}</p>
                    
                    <div className="flex items-center gap-4 mt-2">
                      <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-[6px] px-3 py-2">
                        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Trigger</span>
                        <span className="text-xs font-medium text-zinc-300">{pipeline.trigger}</span>
                      </div>
                      <ArrowRight size={14} className="text-zinc-600" />
                      <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-[6px] px-3 py-2">
                        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Action</span>
                        <span className="text-xs font-medium text-zinc-300">{pipeline.action}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-6">
                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      {pipeline.status === 'active' ? (
                        <button className="p-2 text-zinc-400 hover:text-amber-400 hover:bg-amber-500/10 rounded-[6px] transition-colors" title="Pause">
                          <Pause size={16} />
                        </button>
                      ) : (
                        <button className="p-2 text-zinc-400 hover:text-emerald-400 hover:bg-emerald-500/10 rounded-[6px] transition-colors" title="Resume">
                          <Play size={16} />
                        </button>
                      )}
                      <button className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-[6px] transition-colors" title="Settings">
                        <Settings size={16} />
                      </button>
                    </div>
                    <div className="flex items-center gap-2 text-xs font-mono text-zinc-500">
                      <span>Last run: {pipeline.lastRun}</span>
                    </div>
                  </div>

                </div>
              ))}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
