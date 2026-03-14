import { X, Building2, ExternalLink, Sparkles, Maximize2 } from "lucide-react";

export function CompanySidePanel({ entityId, onClose, onExpand }: { entityId: string, onClose: () => void, onExpand?: () => void }) {
  // Mock data based on the selected entity
  const isCyberSec = entityId === "BE0112233445";
  
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-5 border-b border-zinc-800 shrink-0 bg-zinc-950/50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-[8px] bg-zinc-900 border border-zinc-800 flex items-center justify-center">
            <Building2 size={18} className="text-zinc-400" />
          </div>
          <div>
            <h2 className="text-base font-medium text-zinc-100">
              {isCyberSec ? "CyberSec Partners" : "TechCorp Belgium NV"}
            </h2>
            <div className="flex items-center gap-2 text-[10px] font-mono text-zinc-500 mt-0.5">
              <span>{entityId}</span>
              <span className="w-0.5 h-0.5 rounded-full bg-zinc-700"></span>
              <span>Last sync: 2m ago</span>
              <span className="w-0.5 h-0.5 rounded-full bg-zinc-700"></span>
              <span className="text-emerald-500/80">Confidence: High</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {onExpand && (
            <button onClick={onExpand} className="p-1.5 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 rounded-[4px] transition-colors" title="Open 360 View">
              <Maximize2 size={16} />
            </button>
          )}
          <button onClick={onClose} className="p-1.5 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 rounded-[4px] transition-colors">
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-6">
        
        {/* Linked Systems */}
        <div className="flex flex-col gap-2.5">
          <div className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Linked Systems</div>
          <div className="flex flex-wrap gap-2">
            <Badge source="Teamleader" status="active" />
            <Badge source="Exact Online" status={isCyberSec ? "warning" : "active"} />
            <Badge source="Autotask" status="active" />
            <Badge source="Resend" status="active" />
            <Badge source="Tracardi" status="active" />
          </div>
        </div>

        {/* Executive Summary */}
        <div className="flex flex-col gap-2.5 bg-zinc-900/50 border border-zinc-800 rounded-[6px] p-3">
          <div className="flex items-center gap-4">
            <div className="flex-1 flex flex-col gap-1 border-r border-zinc-800">
              <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Overall Health</span>
              <span className={`text-xs font-medium ${isCyberSec ? 'text-amber-400' : 'text-emerald-400'}`}>
                {isCyberSec ? 'At Risk' : 'Expansion Ready'}
              </span>
            </div>
            <div className="flex-1 flex flex-col gap-1 pl-1">
              <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Primary Play</span>
              <span className="text-xs font-medium text-indigo-400">
                {isCyberSec ? 'Support Recovery' : 'Upsell'}
              </span>
            </div>
          </div>
          <div className="pt-2.5 border-t border-zinc-800/50 flex flex-col gap-1">
             <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Constraint</span>
             <span className="text-xs text-rose-400/90">
               {isCyberSec ? 'Missing financial data blocks automated outreach' : 'Resolve support friction before expanding'}
             </span>
          </div>
        </div>

        {/* AI Next-Best Action */}
        <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-[6px] p-4 flex items-start gap-3">
          <Sparkles size={16} className="text-indigo-400 mt-0.5 shrink-0" />
          <div className="flex flex-col gap-1.5">
            <h4 className="text-xs font-medium text-indigo-300 uppercase tracking-wider">AI Next-Best Action</h4>
            <p className="text-xs text-indigo-200/80 leading-relaxed">
              {isCyberSec ? (
                <>Exact Online sync is currently failing for this account. <strong className="text-indigo-200 font-medium">Recommendation:</strong> Trigger a manual re-sync in the pipeline dashboard before running financial segments.</>
              ) : (
                <>High YTD revenue but 2 open support tickets. <strong className="text-indigo-200 font-medium">Recommendation:</strong> Pause automated marketing emails via Resend until tickets are resolved. Alert Account Manager.</>
              )}
            </p>
          </div>
        </div>

        {/* Data Cards */}
        <div className="flex flex-col gap-4">
          {/* Tracardi */}
          <PanelCard title="Profile Signals" source="Tracardi">
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-2">
                <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Target Segments</span>
                <div className="flex flex-wrap gap-1.5">
                  <span className="px-2 py-1 bg-zinc-900 border border-zinc-800 rounded-[4px] text-[10px] text-zinc-300">High Value</span>
                  <span className="px-2 py-1 bg-zinc-900 border border-zinc-800 rounded-[4px] text-[10px] text-zinc-300">Tech Sector</span>
                  {!isCyberSec && (
                    <span className="px-2 py-1 bg-rose-500/10 border border-rose-500/20 rounded-[4px] text-[10px] text-rose-400">Support Risk</span>
                  )}
                </div>
              </div>
            </div>
          </PanelCard>

          {/* Exact Online */}
          <PanelCard title="Financials" source="Exact Online">
            {isCyberSec ? (
              <div className="text-xs text-amber-400/80 py-2 text-center font-mono">
                Data feed unavailable
              </div>
            ) : (
              <>
                <DataRow label="YTD Revenue" value="€142,500.00" isHighlight isMono />
                <DataRow label="Outstanding" value="€12,450.00" isMono />
                <DataRow label="Credit Limit" value="€50,000.00" isMono />
              </>
            )}
          </PanelCard>

          {/* Teamleader */}
          <PanelCard title="Commercial State" source="Teamleader">
            <DataRow label="Lifecycle Stage" value="Customer" />
            <DataRow label="Account Manager" value={isCyberSec ? "Jan Mertens" : "Sarah Peeters"} />
            <DataRow label="Industry" value="Technology" />
          </PanelCard>

          {/* Autotask */}
          <PanelCard title="Support Tickets" source="Autotask">
            <DataRow label="Open Tickets" value={isCyberSec ? "1" : "2"} isHighlight={!isCyberSec} isMono />
            <DataRow label="Avg Resolution" value="4.2 hrs" isMono />
            <DataRow label="SLA Status" value="Healthy" />
          </PanelCard>

          {/* Resend */}
          <PanelCard title="Email Engagement" source="Resend">
            <DataRow label="Last Email Sent" value="2026-03-11" isMono />
            <DataRow label="Open Rate (30d)" value="68%" isHighlight isMono />
            <DataRow label="Click Rate (30d)" value="12%" isMono />
          </PanelCard>
        </div>
      </div>
    </div>
  );
}

function Badge({ source, status }: { source: string, status: "active" | "warning" }) {
  return (
    <div className={`flex items-center gap-1.5 px-2 py-1 bg-zinc-900 border ${status === 'warning' ? 'border-amber-500/30' : 'border-zinc-800'} rounded-[4px]`}>
      <div className={`w-1.5 h-1.5 rounded-full ${status === 'active' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
      <span className={`text-[10px] font-mono ${status === 'warning' ? 'text-amber-400' : 'text-zinc-400'}`}>{source}</span>
    </div>
  );
}

function PanelCard({ title, source, children }: { title: string, source: string, children: React.ReactNode }) {
  return (
    <div className="border border-zinc-800 rounded-[6px] bg-[#0a0a0a] overflow-hidden">
      <div className="px-3 py-2.5 border-b border-zinc-800 bg-zinc-900/50 flex items-center justify-between">
        <span className="text-xs font-medium text-zinc-300">{title}</span>
        <span className="text-[9px] font-mono text-zinc-500 uppercase tracking-wider">{source}</span>
      </div>
      <div className="p-3 flex flex-col gap-2.5">
        {children}
      </div>
    </div>
  );
}

function DataRow({ label, value, isHighlight, isMono }: { label: string, value: string, isHighlight?: boolean, isMono?: boolean }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-zinc-500">{label}</span>
      <span className={`${isMono ? 'font-mono' : ''} ${isHighlight ? 'text-emerald-400' : 'text-zinc-300'}`}>
        {value}
      </span>
    </div>
  );
}
