import { Building2, ArrowLeft, ExternalLink, Mail, Phone, MapPin, Clock, Activity, FileText, DollarSign, Users, AlertTriangle } from "lucide-react";
import { useState } from "react";

interface Company360ViewProps {
  companyId: string;
  onBack: () => void;
}

export function Company360View({ companyId, onBack }: Company360ViewProps) {
  const [activeTab, setActiveTab] = useState<"summary" | "timeline" | "financials" | "contacts">("summary");

  // Mock data for the selected company
  const company = {
    id: companyId,
    name: "TechCorp Belgium NV",
    domain: "techcorp.be",
    industry: "Software Development",
    employees: "50-200",
    revenue: "€1.2M - €5M",
    health: "Healthy",
    healthScore: 92,
    arr: "€124,000",
    renewalDate: "Oct 15, 2026",
    location: "Brussels, BE",
    description: "Leading provider of enterprise software solutions for the European market. Specializes in cloud infrastructure and cybersecurity consulting.",
    sources: [
      { name: "Exact Online", status: "synced", lastSync: "10m ago" },
      { name: "Teamleader", status: "synced", lastSync: "1h ago" },
      { name: "Autotask", status: "delayed", lastSync: "4h ago" }
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
            <div className="w-8 h-8 rounded-[6px] bg-zinc-800 border border-zinc-700 flex items-center justify-center">
              <Building2 size={16} className="text-zinc-400" />
            </div>
            <div className="flex flex-col">
              <h1 className="text-lg font-medium text-zinc-100 leading-tight">{company.name}</h1>
              <span className="text-xs text-zinc-500 font-mono">{company.domain}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button className="text-sm font-medium text-zinc-400 hover:text-zinc-200 transition-colors px-3 py-1.5 flex items-center gap-2">
            <ExternalLink size={14} />
            Open in CRM
          </button>
          <button className="bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
            Edit Profile
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto p-8 flex flex-col gap-8">
          
          {/* Top Overview Section */}
          <div className="grid grid-cols-12 gap-6">
            {/* Main Info Card */}
            <div className="col-span-8 bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex flex-col gap-6">
              <div className="flex justify-between items-start">
                <div className="flex flex-col gap-2 max-w-2xl">
                  <h2 className="text-xl font-medium text-zinc-100">Company Overview</h2>
                  <p className="text-sm text-zinc-400 leading-relaxed">{company.description}</p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Health Score</span>
                  <div className="flex items-center gap-2">
                    <span className="text-3xl font-medium text-emerald-400">{company.healthScore}</span>
                    <span className="text-sm text-zinc-500">/ 100</span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-4 gap-4 pt-4 border-t border-zinc-800/50">
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-zinc-500 flex items-center gap-1.5"><MapPin size={12} /> Location</span>
                  <span className="text-sm font-medium text-zinc-200">{company.location}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-zinc-500 flex items-center gap-1.5"><Users size={12} /> Employees</span>
                  <span className="text-sm font-medium text-zinc-200">{company.employees}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-zinc-500 flex items-center gap-1.5"><DollarSign size={12} /> ARR</span>
                  <span className="text-sm font-medium text-zinc-200">{company.arr}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-zinc-500 flex items-center gap-1.5"><Clock size={12} /> Renewal</span>
                  <span className="text-sm font-medium text-zinc-200">{company.renewalDate}</span>
                </div>
              </div>
            </div>

            {/* Data Sources Card */}
            <div className="col-span-4 bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex flex-col gap-4">
              <h3 className="text-sm font-medium text-zinc-100">Data Sources</h3>
              <div className="flex flex-col gap-3">
                {company.sources.map((source, i) => (
                  <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/50">
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full ${source.status === 'synced' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                      <span className="text-sm font-medium text-zinc-300">{source.name}</span>
                    </div>
                    <span className="text-xs text-zinc-500 font-mono">{source.lastSync}</span>
                  </div>
                ))}
              </div>
              <div className="mt-auto pt-4 border-t border-zinc-800/50">
                <div className="flex items-start gap-2 text-amber-500/80 bg-amber-500/10 p-2 rounded-[6px] border border-amber-500/20">
                  <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                  <span className="text-xs">Autotask sync is delayed. Ticket data may be stale.</span>
                </div>
              </div>
            </div>
          </div>

          {/* Tabs Navigation */}
          <div className="flex items-center gap-6 border-b border-zinc-800">
            <button 
              onClick={() => setActiveTab("summary")}
              className={`pb-3 text-sm font-medium transition-colors border-b-2 ${activeTab === "summary" ? "border-emerald-500 text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-300"}`}
            >
              Summary
            </button>
            <button 
              onClick={() => setActiveTab("timeline")}
              className={`pb-3 text-sm font-medium transition-colors border-b-2 ${activeTab === "timeline" ? "border-emerald-500 text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-300"}`}
            >
              Activity Timeline
            </button>
            <button 
              onClick={() => setActiveTab("financials")}
              className={`pb-3 text-sm font-medium transition-colors border-b-2 ${activeTab === "financials" ? "border-emerald-500 text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-300"}`}
            >
              Financials
            </button>
            <button 
              onClick={() => setActiveTab("contacts")}
              className={`pb-3 text-sm font-medium transition-colors border-b-2 ${activeTab === "contacts" ? "border-emerald-500 text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-300"}`}
            >
              Contacts (12)
            </button>
          </div>

          {/* Tab Content Area */}
          <div className="flex flex-col gap-6 pb-12">
            {activeTab === "summary" && <SummaryTab />}
            {activeTab === "timeline" && <TimelineTab />}
            {activeTab === "financials" && <FinancialsTab />}
            {activeTab === "contacts" && <ContactsTab />}
          </div>

        </div>
      </div>
    </div>
  );
}

function SummaryTab() {
  return (
    <div className="grid grid-cols-2 gap-6">
      {/* Key Attributes */}
      <div className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex flex-col gap-4">
        <h3 className="text-sm font-medium text-zinc-100">Key Attributes</h3>
        <div className="flex flex-col gap-3">
          <div className="flex justify-between py-2 border-b border-zinc-800/50">
            <span className="text-sm text-zinc-500">Industry</span>
            <span className="text-sm font-medium text-zinc-300">Software Development</span>
          </div>
          <div className="flex justify-between py-2 border-b border-zinc-800/50">
            <span className="text-sm text-zinc-500">Founded</span>
            <span className="text-sm font-medium text-zinc-300">2015</span>
          </div>
          <div className="flex justify-between py-2 border-b border-zinc-800/50">
            <span className="text-sm text-zinc-500">Tech Stack</span>
            <div className="flex gap-2">
              <span className="px-2 py-0.5 bg-zinc-800 rounded text-xs text-zinc-300">AWS</span>
              <span className="px-2 py-0.5 bg-zinc-800 rounded text-xs text-zinc-300">React</span>
              <span className="px-2 py-0.5 bg-zinc-800 rounded text-xs text-zinc-300">Node.js</span>
            </div>
          </div>
          <div className="flex justify-between py-2">
            <span className="text-sm text-zinc-500">Account Owner</span>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-[10px] font-medium">
                JD
              </div>
              <span className="text-sm font-medium text-zinc-300">Jane Doe</span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Signals */}
      <div className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex flex-col gap-4">
        <h3 className="text-sm font-medium text-zinc-100">Recent Signals</h3>
        <div className="flex flex-col gap-4">
          <div className="flex gap-3 items-start">
            <div className="w-8 h-8 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0 mt-0.5">
              <Activity size={14} className="text-emerald-400" />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium text-zinc-200">High Product Usage</span>
              <span className="text-xs text-zinc-500">Active users increased by 24% in the last 30 days.</span>
              <span className="text-xs text-zinc-600 font-mono mt-1">2 days ago</span>
            </div>
          </div>
          <div className="flex gap-3 items-start">
            <div className="w-8 h-8 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center shrink-0 mt-0.5">
              <AlertTriangle size={14} className="text-amber-400" />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium text-zinc-200">Support Ticket Spike</span>
              <span className="text-xs text-zinc-500">5 high-priority tickets opened regarding API performance.</span>
              <span className="text-xs text-zinc-600 font-mono mt-1">5 days ago</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TimelineTab() {
  const events = [
    { type: "email", title: "Quarterly Review Email Sent", date: "Today, 10:30 AM", user: "Jane Doe", detail: "Opened at 11:15 AM" },
    { type: "ticket", title: "Support Ticket Resolved", date: "Yesterday, 14:20 PM", user: "Support Team", detail: "Issue with API rate limits." },
    { type: "meeting", title: "Check-in Call", date: "Oct 12, 2025", user: "Jane Doe", detail: "Discussed Q4 roadmap and expansion." },
    { type: "invoice", title: "Invoice #INV-2025-089 Paid", date: "Oct 01, 2025", user: "System", detail: "€10,400.00 processed via Stripe." },
  ];

  return (
    <div className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6">
      <div className="flex flex-col gap-6">
        {events.map((event, i) => (
          <div key={i} className="flex gap-4">
            <div className="flex flex-col items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-zinc-900 border border-zinc-700 flex items-center justify-center shrink-0 z-10">
                {event.type === 'email' && <Mail size={14} className="text-blue-400" />}
                {event.type === 'ticket' && <AlertTriangle size={14} className="text-amber-400" />}
                {event.type === 'meeting' && <Phone size={14} className="text-emerald-400" />}
                {event.type === 'invoice' && <FileText size={14} className="text-purple-400" />}
              </div>
              {i !== events.length - 1 && <div className="w-px h-full bg-zinc-800"></div>}
            </div>
            <div className="flex flex-col gap-1 pb-6">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-zinc-200">{event.title}</span>
                <span className="text-xs text-zinc-500 font-mono">{event.date}</span>
              </div>
              <span className="text-sm text-zinc-400">{event.detail}</span>
              <span className="text-xs text-zinc-600 mt-1">by {event.user}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FinancialsTab() {
  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-3 gap-6">
        <div className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex flex-col gap-2">
          <span className="text-sm text-zinc-500">Total Lifetime Value</span>
          <span className="text-2xl font-medium text-zinc-100">€342,500</span>
          <span className="text-xs text-emerald-500 flex items-center gap-1 mt-2">
            +12% YoY
          </span>
        </div>
        <div className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex flex-col gap-2">
          <span className="text-sm text-zinc-500">Current ARR</span>
          <span className="text-2xl font-medium text-zinc-100">€124,000</span>
          <span className="text-xs text-zinc-500 mt-2">Renews Oct 15, 2026</span>
        </div>
        <div className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex flex-col gap-2">
          <span className="text-sm text-zinc-500">Outstanding Invoices</span>
          <span className="text-2xl font-medium text-amber-500">€10,400</span>
          <span className="text-xs text-amber-500/80 mt-2">1 invoice overdue (5 days)</span>
        </div>
      </div>

      <div className="bg-[#0a0a0a] border border-zinc-800 rounded-xl overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/50">
              <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Invoice</th>
              <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Date</th>
              <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Amount</th>
              <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            <tr className="hover:bg-zinc-900/30 transition-colors">
              <td className="px-6 py-4 text-sm font-medium text-zinc-300">INV-2025-090</td>
              <td className="px-6 py-4 text-sm text-zinc-500">Nov 01, 2025</td>
              <td className="px-6 py-4 text-sm text-zinc-300 font-mono">€10,400.00</td>
              <td className="px-6 py-4">
                <span className="px-2 py-1 rounded-full bg-amber-500/10 text-amber-500 text-xs font-medium border border-amber-500/20">Overdue</span>
              </td>
            </tr>
            <tr className="hover:bg-zinc-900/30 transition-colors">
              <td className="px-6 py-4 text-sm font-medium text-zinc-300">INV-2025-089</td>
              <td className="px-6 py-4 text-sm text-zinc-500">Oct 01, 2025</td>
              <td className="px-6 py-4 text-sm text-zinc-300 font-mono">€10,400.00</td>
              <td className="px-6 py-4">
                <span className="px-2 py-1 rounded-full bg-emerald-500/10 text-emerald-500 text-xs font-medium border border-emerald-500/20">Paid</span>
              </td>
            </tr>
            <tr className="hover:bg-zinc-900/30 transition-colors">
              <td className="px-6 py-4 text-sm font-medium text-zinc-300">INV-2025-088</td>
              <td className="px-6 py-4 text-sm text-zinc-500">Sep 01, 2025</td>
              <td className="px-6 py-4 text-sm text-zinc-300 font-mono">€10,400.00</td>
              <td className="px-6 py-4">
                <span className="px-2 py-1 rounded-full bg-emerald-500/10 text-emerald-500 text-xs font-medium border border-emerald-500/20">Paid</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ContactsTab() {
  return (
    <div className="bg-[#0a0a0a] border border-zinc-800 rounded-xl overflow-hidden">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="border-b border-zinc-800 bg-zinc-900/50">
            <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Name</th>
            <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Role</th>
            <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Email</th>
            <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Last Active</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800">
          <tr className="hover:bg-zinc-900/30 transition-colors">
            <td className="px-6 py-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs font-medium text-zinc-300">
                  MV
                </div>
                <span className="text-sm font-medium text-zinc-200">Marc Vandamme</span>
              </div>
            </td>
            <td className="px-6 py-4 text-sm text-zinc-400">CTO</td>
            <td className="px-6 py-4 text-sm text-zinc-500">marc.v@techcorp.be</td>
            <td className="px-6 py-4 text-sm text-zinc-500 font-mono">2h ago</td>
          </tr>
          <tr className="hover:bg-zinc-900/30 transition-colors">
            <td className="px-6 py-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs font-medium text-zinc-300">
                  SL
                </div>
                <span className="text-sm font-medium text-zinc-200">Sophie Leroy</span>
              </div>
            </td>
            <td className="px-6 py-4 text-sm text-zinc-400">VP Engineering</td>
            <td className="px-6 py-4 text-sm text-zinc-500">sophie.l@techcorp.be</td>
            <td className="px-6 py-4 text-sm text-zinc-500 font-mono">1d ago</td>
          </tr>
          <tr className="hover:bg-zinc-900/30 transition-colors">
            <td className="px-6 py-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs font-medium text-zinc-300">
                  TD
                </div>
                <span className="text-sm font-medium text-zinc-200">Tom Dubois</span>
              </div>
            </td>
            <td className="px-6 py-4 text-sm text-zinc-400">Procurement Manager</td>
            <td className="px-6 py-4 text-sm text-zinc-500">tom.d@techcorp.be</td>
            <td className="px-6 py-4 text-sm text-zinc-500 font-mono">5d ago</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
