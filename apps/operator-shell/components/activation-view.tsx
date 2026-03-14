import { Zap, Play, Pause, Settings, ArrowRight, History, GitBranch, ShieldCheck, Search } from "lucide-react";
import { useState } from "react";
import { PlayDetailView } from "./play-detail-view";

export function ActivationView() {
  const [activeTab, setActiveTab] = useState<"pipelines" | "plays" | "history">("pipelines");
  const [selectedPlayId, setSelectedPlayId] = useState<string | null>(null);

  if (selectedPlayId) {
    return <PlayDetailView playId={selectedPlayId} onBack={() => setSelectedPlayId(null)} />;
  }

  return (
    <div className="flex-1 flex flex-col bg-[#050505] overflow-hidden">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-8 justify-between shrink-0 bg-zinc-950/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-[6px] bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
            <Zap size={16} className="text-amber-400" />
          </div>
          <h1 className="text-lg font-medium text-zinc-100">Activation</h1>
        </div>
        <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-[8px] p-1">
          <button 
            onClick={() => setActiveTab("pipelines")}
            className={`px-3 py-1.5 text-sm font-medium rounded-[4px] transition-colors ${activeTab === 'pipelines' ? 'bg-zinc-800 text-zinc-100' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            Pipelines
          </button>
          <button 
            onClick={() => setActiveTab("plays")}
            className={`px-3 py-1.5 text-sm font-medium rounded-[4px] transition-colors ${activeTab === 'plays' ? 'bg-zinc-800 text-zinc-100' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            Plays
          </button>
          <button 
            onClick={() => setActiveTab("history")}
            className={`px-3 py-1.5 text-sm font-medium rounded-[4px] transition-colors ${activeTab === 'history' ? 'bg-zinc-800 text-zinc-100' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            History
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-6xl mx-auto flex flex-col gap-6">
          {activeTab === "pipelines" && <PipelinesTab />}
          {activeTab === "plays" && <PlaysTab onSelectPlay={setSelectedPlayId} />}
          {activeTab === "history" && <HistoryTab />}
        </div>
      </div>
    </div>
  );
}

function PipelinesTab() {
  const [searchQuery, setSearchQuery] = useState("");

  const pipelines = [
    { id: "pipe_1", name: "Daily CDP Sync", description: "Syncs 'Tech Enterprise Active' segment to Tracardi.", trigger: "Schedule: Daily at 00:00", action: "Tracardi: Update Profiles", status: "active", lastRun: "10h ago" },
    { id: "pipe_2", name: "Support Friction Pause", description: "Pauses marketing emails if open Autotask tickets > 0.", trigger: "Event: Ticket Created", action: "Resend: Remove from Audience", status: "active", lastRun: "2m ago" },
    { id: "pipe_3", name: "Churn Risk Alert", description: "Notifies Account Manager when engagement drops.", trigger: "Schedule: Weekly", action: "Slack: Send Alert", status: "paused", lastRun: "5d ago" },
  ];

  const filteredPipelines = pipelines.filter(p => 
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    p.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center mb-2">
        <div className="flex items-center gap-4">
          <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider">Active Pipelines</h2>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={14} />
            <input 
              type="text" 
              placeholder="Search pipelines..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded-[6px] py-1 pl-8 pr-3 text-xs text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-600 w-48"
            />
          </div>
        </div>
        <button className="bg-zinc-100 hover:bg-white text-zinc-900 px-3 py-1.5 text-xs font-medium rounded-[4px] transition-colors">
          Create Pipeline
        </button>
      </div>
      
      {filteredPipelines.length > 0 ? (
        filteredPipelines.map(pipeline => (
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
        ))
      ) : (
        <div className="flex flex-col items-center justify-center py-20 border border-zinc-800 border-dashed rounded-xl bg-zinc-900/20">
          <Search size={32} className="text-zinc-600 mb-4" />
          <h3 className="text-base font-medium text-zinc-300 mb-1">No pipelines found</h3>
          <p className="text-sm text-zinc-500">Try adjusting your search query.</p>
        </div>
      )}
    </div>
  );
}

function PlaysTab({ onSelectPlay }: { onSelectPlay: (id: string) => void }) {
  const [searchQuery, setSearchQuery] = useState("");

  const plays = [
    { id: "play_1", name: "Upsell: Enterprise Tier", description: "Target healthy accounts near seat limits.", target: "Healthy, >80% utilization", channel: "Sales Outreach", confidence: "High" },
    { id: "play_2", name: "Support Recovery", description: "Pause marketing and notify AM for accounts with >3 open tickets.", target: "Active, >3 tickets", channel: "Slack Alert", confidence: "High" },
    { id: "play_3", name: "Re-engagement Sequence", description: "Automated Resend sequence for accounts inactive > 90 days.", target: "Inactive > 90d", channel: "Resend Email", confidence: "Medium" },
  ];

  const filteredPlays = plays.filter(p => 
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    p.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center mb-2">
        <div className="flex items-center gap-4">
          <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider">Available Plays</h2>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={14} />
            <input 
              type="text" 
              placeholder="Search plays..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded-[6px] py-1 pl-8 pr-3 text-xs text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-600 w-48"
            />
          </div>
        </div>
      </div>

      {filteredPlays.length > 0 ? (
        <div className="grid grid-cols-3 gap-6">
          {filteredPlays.map(play => (
            <div 
              key={play.id} 
              onClick={() => onSelectPlay(play.id)}
              className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-5 flex flex-col gap-4 hover:border-zinc-700 transition-colors cursor-pointer group"
            >
              <div className="flex items-start justify-between">
                <div className="w-10 h-10 rounded-[8px] bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                  <ShieldCheck size={20} className="text-indigo-400" />
                </div>
                <span className={`text-[10px] font-mono uppercase tracking-wider px-2 py-1 rounded-[4px] border ${
                  play.confidence === 'High' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                }`}>
                  {play.confidence} Match
                </span>
              </div>
              <div className="flex flex-col gap-1">
                <h3 className="text-base font-medium text-zinc-200 group-hover:text-indigo-400 transition-colors">{play.name}</h3>
                <p className="text-xs text-zinc-500">{play.description}</p>
              </div>
              <div className="flex flex-col gap-2 mt-2 pt-4 border-t border-zinc-800">
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-500">Target</span>
                  <span className="font-mono text-zinc-300">{play.target}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-500">Channel</span>
                  <span className="font-mono text-zinc-300">{play.channel}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-20 border border-zinc-800 border-dashed rounded-xl bg-zinc-900/20">
          <Search size={32} className="text-zinc-600 mb-4" />
          <h3 className="text-base font-medium text-zinc-300 mb-1">No plays found</h3>
          <p className="text-sm text-zinc-500">Try adjusting your search query.</p>
        </div>
      )}
    </div>
  );
}

function HistoryTab() {
  return (
    <div className="flex flex-col items-center justify-center py-20 border border-zinc-800 border-dashed rounded-xl bg-zinc-900/20">
      <History size={32} className="text-zinc-600 mb-4" />
      <h3 className="text-base font-medium text-zinc-300 mb-1">No recent activations</h3>
      <p className="text-sm text-zinc-500">Your activation history will appear here once you run a pipeline or play.</p>
    </div>
  );
}
