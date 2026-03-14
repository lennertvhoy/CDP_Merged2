import { ArrowLeft, ShieldCheck, Play, Settings, Users, ArrowRight, Zap, CheckCircle2 } from "lucide-react";

interface PlayDetailViewProps {
  playId: string;
  onBack: () => void;
}

export function PlayDetailView({ playId, onBack }: PlayDetailViewProps) {
  // Mock data for the selected play
  const play = {
    id: playId,
    name: "Upsell: Enterprise Tier",
    description: "Target healthy accounts nearing their seat limits with an automated outreach sequence and alert the Account Manager.",
    status: "active",
    confidence: "High",
    stats: {
      eligible: 142,
      enrolled: 89,
      converted: 12,
      conversionRate: "13.5%"
    },
    trigger: {
      type: "Segment Entry",
      segmentName: "Healthy & High Utilization",
      conditions: [
        "Health Score > 80",
        "Seat Utilization > 85%",
        "ARR > €50k"
      ]
    },
    actions: [
      { step: 1, type: "Resend", name: "Send 'Upgrade Options' Email", delay: "Immediate" },
      { step: 2, type: "Wait", name: "Wait for 3 days", delay: "3 Days" },
      { step: 3, type: "Condition", name: "If Email Opened", delay: "Immediate" },
      { step: 4, type: "Slack", name: "Alert Account Manager", delay: "Immediate" }
    ]
  };

  return (
    <div className="flex-1 flex flex-col bg-[#050505] overflow-hidden">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-8 justify-between shrink-0 bg-zinc-950/50">
        <div className="flex items-center gap-4">
          <button 
            onClick={onBack}
            className="w-8 h-8 rounded-[6px] hover:bg-zinc-800 flex items-center justify-center text-zinc-400 transition-colors"
          >
            <ArrowLeft size={16} />
          </button>
          <div className="w-px h-6 bg-zinc-800"></div>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-[6px] bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
              <ShieldCheck size={16} className="text-indigo-400" />
            </div>
            <div className="flex flex-col">
              <h1 className="text-lg font-medium text-zinc-100 leading-tight">{play.name}</h1>
              <span className="text-xs text-zinc-500 font-mono">Play ID: {play.id}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-[6px] border ${
            play.status === 'active' 
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
              : 'bg-zinc-800 border-zinc-700 text-zinc-400'
          }`}>
            <div className={`w-1.5 h-1.5 rounded-full ${play.status === 'active' ? 'bg-emerald-500' : 'bg-zinc-500'}`} />
            <span className="text-xs font-medium uppercase tracking-wider">{play.status}</span>
          </div>
          <div className="w-px h-6 bg-zinc-800 mx-1"></div>
          <button className="bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors flex items-center gap-2">
            <Play size={14} />
            Run Now
          </button>
          <button className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-[6px] transition-colors" title="Settings">
            <Settings size={16} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-5xl mx-auto flex flex-col gap-8">
          
          {/* Overview & Stats */}
          <div className="grid grid-cols-3 gap-6">
            <div className="col-span-2 bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex flex-col gap-4">
              <h2 className="text-base font-medium text-zinc-100">Play Overview</h2>
              <p className="text-sm text-zinc-400 leading-relaxed">{play.description}</p>
              
              <div className="mt-4 pt-4 border-t border-zinc-800/50 grid grid-cols-2 gap-6">
                <div className="flex flex-col gap-2">
                  <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Trigger Source</span>
                  <div className="flex items-center gap-2">
                    <Users size={14} className="text-zinc-400" />
                    <span className="text-sm font-medium text-zinc-200">{play.trigger.segmentName}</span>
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Match Confidence</span>
                  <span className="text-sm font-medium text-emerald-400">{play.confidence}</span>
                </div>
              </div>
            </div>

            <div className="col-span-1 bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex flex-col gap-6">
              <h2 className="text-base font-medium text-zinc-100">Performance</h2>
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1">
                  <span className="text-2xl font-medium text-zinc-100">{play.stats.eligible}</span>
                  <span className="text-xs text-zinc-500">Eligible</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-2xl font-medium text-indigo-400">{play.stats.enrolled}</span>
                  <span className="text-xs text-zinc-500">Enrolled</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-2xl font-medium text-emerald-400">{play.stats.converted}</span>
                  <span className="text-xs text-zinc-500">Converted</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-2xl font-medium text-zinc-100">{play.stats.conversionRate}</span>
                  <span className="text-xs text-zinc-500">Rate</span>
                </div>
              </div>
            </div>
          </div>

          {/* Workflow Builder Visualization */}
          <div className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex flex-col gap-6">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-medium text-zinc-100">Workflow Definition</h2>
              <button className="text-sm font-medium text-indigo-400 hover:text-indigo-300 transition-colors">
                Edit Workflow
              </button>
            </div>

            <div className="flex flex-col items-center py-8 relative">
              {/* Vertical Line */}
              <div className="absolute top-8 bottom-8 left-1/2 -translate-x-1/2 w-px bg-zinc-800 z-0"></div>

              {/* Trigger Node */}
              <div className="relative z-10 bg-zinc-900 border border-zinc-700 rounded-xl p-4 w-80 shadow-xl mb-8 flex flex-col gap-3">
                <div className="flex items-center gap-2 text-zinc-300">
                  <Zap size={16} className="text-amber-400" />
                  <span className="text-sm font-medium">Trigger: {play.trigger.type}</span>
                </div>
                <div className="bg-zinc-950 rounded-lg p-3 border border-zinc-800/50 flex flex-col gap-2">
                  <span className="text-xs font-medium text-zinc-400">Segment: {play.trigger.segmentName}</span>
                  <div className="flex flex-col gap-1">
                    {play.trigger.conditions.map((cond, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-zinc-500 font-mono">
                        <CheckCircle2 size={10} className="text-emerald-500/50" />
                        {cond}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Action Nodes */}
              {play.actions.map((action, i) => (
                <div key={i} className="relative z-10 flex flex-col items-center mb-8 last:mb-0">
                  {/* Delay Label */}
                  {action.delay !== "Immediate" && (
                    <div className="bg-zinc-900 border border-zinc-800 rounded-full px-3 py-1 text-[10px] font-mono text-zinc-400 mb-8 z-10">
                      Wait: {action.delay}
                    </div>
                  )}
                  
                  {/* Action Card */}
                  <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 w-80 shadow-xl flex items-center gap-4">
                    <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center shrink-0 text-xs font-medium text-zinc-400 border border-zinc-700">
                      {action.step}
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">{action.type}</span>
                      <span className="text-sm font-medium text-zinc-200">{action.name}</span>
                    </div>
                  </div>
                </div>
              ))}

            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
