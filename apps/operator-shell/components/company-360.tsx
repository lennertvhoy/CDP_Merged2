import { Building2, ExternalLink, AlertCircle, CheckCircle2, Sparkles } from "lucide-react";

export function Company360() {
  return (
    <div className="flex flex-col gap-6">
      {/* AI Next-Best Action Banner */}
      <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-[6px] p-4 flex items-start gap-3">
        <Sparkles size={16} className="text-indigo-400 mt-0.5 shrink-0" />
        <div className="flex flex-col gap-1">
          <h4 className="text-sm font-medium text-indigo-300">AI Next-Best Action</h4>
          <p className="text-xs text-indigo-200/70 leading-relaxed">
            TechCorp Belgium has high YTD revenue but 2 open support tickets. 
            <strong className="text-indigo-200 font-medium"> Recommendation:</strong> Pause automated marketing emails via Resend until tickets are resolved. Alert Account Manager (Sarah Peeters) to follow up manually.
          </p>
        </div>
      </div>

      {/* Header Section */}
      <div className="flex items-start justify-between pb-6 border-b border-zinc-800">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-medium text-zinc-100 tracking-tight">TechCorp Belgium NV</h1>
            <StatusBadge status="active" />
          </div>
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1.5 text-zinc-400">
              <Building2 size={14} />
              <span>Enterprise</span>
            </div>
            <div className="flex items-center gap-1.5 font-mono text-zinc-500 text-xs">
              <span>VAT:</span>
              <span className="text-zinc-300">BE0412345678</span>
            </div>
          </div>
          <div className="mt-3 text-[10px] font-mono text-zinc-600 flex items-center gap-2">
            <span title="Internal Master ID">ID: cmp_9x8f7a6</span>
          </div>
        </div>
        <ProvenanceBadge source="PostgreSQL" type="primary" />
      </div>

      {/* Grid Layout for Data Cards */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        
        {/* CRM Context (Teamleader) */}
        <DataCard title="CRM Context" source="Teamleader" lastSync="10 mins ago">
          <div className="flex flex-col gap-3">
            <DataRow label="Account Manager" value="Sarah Peeters" />
            <DataRow label="Lifecycle Stage" value="Customer" />
            <DataRow label="Last Contact" value="2026-03-10" isMono />
            <DataRow label="Active Deals" value="2" isMono />
            <div className="mt-2 pt-3 border-t border-zinc-800/50">
              <a href="#" className="text-xs font-mono text-zinc-400 hover:text-zinc-200 flex items-center gap-1 transition-colors">
                View in Teamleader <ExternalLink size={10} />
              </a>
            </div>
          </div>
        </DataCard>

        {/* Financials (Exact) */}
        <DataCard title="Financials" source="Exact Online" lastSync="2 hours ago">
          <div className="flex flex-col gap-3">
            <DataRow label="YTD Revenue" value="€142,500.00" isMono isHighlight />
            <DataRow 
              label="Outstanding Balance" 
              value="Unavailable" 
              isUnavailable 
              unavailableReason="Not provided by Exact SalesInvoice feed" 
            />
            <DataRow label="Overdue" value="—" isMono isNull />
            <DataRow label="Payment Term" value="30 Days" />
            <div className="mt-2 pt-3 border-t border-zinc-800/50">
              <a href="#" className="text-xs font-mono text-zinc-400 hover:text-zinc-200 flex items-center gap-1 transition-colors">
                View in Exact <ExternalLink size={10} />
              </a>
            </div>
          </div>
        </DataCard>

        {/* Support/Tickets (Autotask) - UNLINKED STATE */}
        <DataCard title="Support Tickets" source="Autotask" lastSync="5 mins ago">
          <div className="flex flex-col gap-3">
            <DataRow label="Open Tickets" value="2" isMono isHighlight />
            <DataRow label="Avg Resolution" value="4.2 hrs" isMono />
            <DataRow label="Escalated" value="0" isMono />
            <DataRow label="SLA Status" value="Healthy" />
            <div className="mt-2 pt-3 border-t border-zinc-800/50">
              <a href="#" className="text-xs font-mono text-zinc-400 hover:text-zinc-200 flex items-center gap-1 transition-colors">
                View in Autotask <ExternalLink size={10} />
              </a>
            </div>
          </div>
        </DataCard>

        {/* Email Engagement (Resend) */}
        <DataCard title="Email Engagement" source="Resend" lastSync="Live">
          <div className="flex flex-col gap-3">
            <DataRow label="Last Email Sent" value="2026-03-11" isMono />
            <DataRow label="Open Rate (30d)" value="68%" isMono isHighlight />
            <DataRow label="Click Rate (30d)" value="12%" isMono />
            <DataRow label="Bounces" value="0" isMono />
            <div className="mt-2 pt-3 border-t border-zinc-800/50">
              <a href="#" className="text-xs font-mono text-zinc-400 hover:text-zinc-200 flex items-center gap-1 transition-colors">
                View in Resend <ExternalLink size={10} />
              </a>
            </div>
          </div>
        </DataCard>

        {/* Tracardi / Activation Status */}
        <div className="xl:col-span-4">
          <DataCard title="Activation Projection" source="Tracardi" lastSync="Live">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="flex flex-col gap-2">
                <div className="text-xs font-mono text-zinc-500 uppercase tracking-wider">Target Segments</div>
                <div className="flex flex-wrap gap-2">
                  <span className="px-2 py-1 bg-zinc-900 border border-zinc-800 rounded-[4px] text-xs text-zinc-300">High Value</span>
                  <span className="px-2 py-1 bg-zinc-900 border border-zinc-800 rounded-[4px] text-xs text-zinc-300">Tech Sector</span>
                  <span className="px-2 py-1 bg-rose-500/10 border border-rose-500/20 rounded-[4px] text-xs text-rose-400">Support Risk</span>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <div className="text-xs font-mono text-zinc-500 uppercase tracking-wider">Recent Events (Processor)</div>
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-zinc-400">Ticket Opened (Severity 2)</span>
                    <span className="font-mono text-zinc-600">2h ago</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-zinc-400">Email Opened (Product Update)</span>
                    <span className="font-mono text-zinc-600">1d ago</span>
                  </div>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <div className="text-xs font-mono text-zinc-500 uppercase tracking-wider">Data Quality Score</div>
                <div className="flex flex-col gap-1">
                  <div className="flex items-end gap-2">
                    <span className="text-2xl font-mono text-emerald-500 leading-none">92%</span>
                    <span className="text-xs text-zinc-500 mb-0.5">High Confidence</span>
                  </div>
                  <div className="text-[10px] text-zinc-600 leading-tight pr-4">
                    Based on source linkage, field completeness, and recency.
                  </div>
                </div>
              </div>
            </div>
          </DataCard>
        </div>

      </div>
    </div>
  );
}

// --- Subcomponents ---

function DataCard({ 
  title, 
  source, 
  lastSync, 
  isUnlinked = false, 
  children 
}: { 
  title: string; 
  source: string; 
  lastSync?: string; 
  isUnlinked?: boolean; 
  children: React.ReactNode;
}) {
  return (
    <div className={`flex flex-col bg-[#0a0a0a] border rounded-[6px] overflow-hidden ${isUnlinked ? 'border-zinc-800/50 border-dashed' : 'border-zinc-800'}`}>
      <div className={`px-4 py-3 border-b flex items-center justify-between ${isUnlinked ? 'border-zinc-800/50 bg-zinc-950/50' : 'border-zinc-800 bg-zinc-900/20'}`}>
        <h3 className={`text-sm font-medium ${isUnlinked ? 'text-zinc-500' : 'text-zinc-200'}`}>{title}</h3>
        <ProvenanceBadge source={source} type={isUnlinked ? 'unlinked' : 'secondary'} />
      </div>
      <div className={`p-4 flex-1 ${isUnlinked ? 'bg-zinc-950/30' : ''}`}>
        {children}
      </div>
      {!isUnlinked && lastSync && (
        <div className="px-4 py-2 bg-zinc-950/50 border-t border-zinc-800/50 text-[10px] font-mono text-zinc-600 flex justify-between">
          <span>Sync Status</span>
          <span>{lastSync}</span>
        </div>
      )}
    </div>
  );
}

function DataRow({ 
  label, 
  value, 
  isMono = false, 
  isHighlight = false,
  isNull = false,
  isUnavailable = false,
  unavailableReason
}: { 
  label: string; 
  value: string; 
  isMono?: boolean; 
  isHighlight?: boolean;
  isNull?: boolean;
  isUnavailable?: boolean;
  unavailableReason?: string;
}) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-xs text-zinc-500">{label}</span>
      {isUnavailable ? (
        <span 
          title={unavailableReason}
          className="text-[10px] font-mono bg-zinc-900 border border-zinc-800 text-zinc-500 px-1.5 py-0.5 rounded-[4px] cursor-help"
        >
          {value}
        </span>
      ) : (
        <span className={`text-sm ${isMono ? 'font-mono tracking-tight' : ''} ${
          isNull ? 'text-zinc-600' : 
          isHighlight ? 'text-zinc-100 font-medium' : 'text-zinc-300'
        }`}>
          {value}
        </span>
      )}
    </div>
  );
}

function ProvenanceBadge({ source, type = 'secondary' }: { source: string, type?: 'primary' | 'secondary' | 'unlinked' }) {
  const styles = {
    primary: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
    secondary: "bg-zinc-800/50 text-zinc-400 border-zinc-700",
    unlinked: "bg-transparent text-zinc-600 border-zinc-800 border-dashed"
  };

  return (
    <div className={`px-2 py-0.5 rounded-[4px] border text-[10px] font-mono uppercase tracking-wider ${styles[type]}`}>
      [{source}]
    </div>
  );
}

function StatusBadge({ status }: { status: 'active' | 'inactive' }) {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-[4px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
      <CheckCircle2 size={12} />
      <span>Active</span>
    </div>
  );
}
