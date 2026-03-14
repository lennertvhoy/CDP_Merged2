import { useState } from "react";
import { Building2, Search, Filter, Database, Mail, AlertCircle, CheckCircle2, Loader2, AlertTriangle } from "lucide-react";
import { CompanySidePanel } from "./company-side-panel";
import { StateSwitcher, type ViewState } from "./state-switcher";

export function CompaniesView() {
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [viewState, setViewState] = useState<ViewState>("success");

  const companies = [
    { id: "BE0412345678", name: "TechCorp Belgium NV", manager: "Sarah Peeters", status: "Active", systems: ["Exact", "Teamleader", "Autotask"], revenue: "€142,500.00", health: "good" },
    { id: "BE0876543210", name: "DataFlow Systems", manager: "Tom De Smet", status: "Active", systems: ["Exact", "Teamleader"], revenue: "€84,200.00", health: "good" },
    { id: "BE0998877665", name: "CloudNative BV", manager: "Sarah Peeters", status: "Warning", systems: ["Exact", "Autotask"], revenue: "€11,150.00", health: "warning" },
    { id: "BE0112233445", name: "CyberSec Partners", manager: "Jan Mertens", status: "Active", systems: ["Teamleader"], revenue: "Unavailable", health: "good" },
    { id: "BE0554433221", name: "AI Solutions Group", manager: "Tom De Smet", status: "Active", systems: ["Exact", "Teamleader", "Autotask"], revenue: "€108,900.00", health: "good" },
  ];

  return (
    <div className="flex-1 flex flex-col bg-[#050505] overflow-hidden relative">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-8 justify-between shrink-0 bg-zinc-950/50 z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-[6px] bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
            <Building2 size={16} className="text-emerald-400" />
          </div>
          <h1 className="text-lg font-medium text-zinc-100">Companies</h1>
        </div>
        <div className="flex items-center gap-4">
          <StateSwitcher currentState={viewState} onStateChange={setViewState} />
          <button className="bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
            Add Company
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden relative">
        <div className={`flex-1 overflow-y-auto p-8 transition-all duration-300 ${selectedEntity ? 'mr-[420px]' : ''}`}>
          <div className="w-full mx-auto flex flex-col gap-6">
            
            {/* Filters */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={14} />
                  <input 
                    type="text" 
                    placeholder="Search companies..." 
                    className="bg-zinc-900 border border-zinc-800 rounded-[6px] py-1.5 pl-9 pr-4 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-600 w-64"
                  />
                </div>
                <button className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-[6px] text-sm text-zinc-400 hover:text-zinc-200 transition-colors">
                  <Filter size={14} />
                  Filter
                </button>
              </div>
              <div className="text-sm text-zinc-500 font-mono">
                {viewState === "success" || viewState === "partial" ? companies.length : 0} companies total
              </div>
            </div>

            {viewState === "loading" && (
              <div className="flex flex-col items-center justify-center py-24 text-zinc-500">
                <Loader2 size={24} className="animate-spin mb-4 text-emerald-500" />
                <p className="text-sm font-medium">Loading companies...</p>
              </div>
            )}

            {viewState === "empty" && (
              <div className="flex flex-col items-center justify-center py-24 text-zinc-500 border border-dashed border-zinc-800 rounded-[8px] bg-zinc-900/20">
                <Building2 size={32} className="mb-4 text-zinc-600" />
                <p className="text-sm font-medium text-zinc-300">No companies found</p>
                <p className="text-xs mt-1 max-w-sm text-center">You haven't added any companies yet, or your search filters are too restrictive.</p>
                <button className="mt-6 bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
                  Add Company
                </button>
              </div>
            )}

            {viewState === "error" && (
              <div className="flex flex-col items-center justify-center py-24 text-zinc-500 border border-zinc-800 rounded-[8px] bg-rose-500/5">
                <AlertTriangle size={32} className="mb-4 text-rose-500" />
                <p className="text-sm font-medium text-rose-400">Failed to load companies</p>
                <p className="text-xs mt-1 max-w-sm text-center text-zinc-400">There was an error connecting to the customer database. Please try again later.</p>
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
                      <p className="text-amber-500/70 mt-0.5">Exact Online data is currently unavailable. Revenue figures may be missing or outdated.</p>
                    </div>
                  </div>
                )}
                
                {/* Table */}
                <div className="border border-zinc-800 rounded-[8px] bg-[#0a0a0a] overflow-hidden">
                  <table className="w-full text-left border-collapse whitespace-nowrap">
                    <thead>
                      <tr className="border-b border-zinc-800 bg-zinc-900/50">
                        <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Company Name</th>
                        <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">VAT Number</th>
                        <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Account Manager</th>
                        <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Linked Systems</th>
                        <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider text-right">Revenue</th>
                        <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800">
                      {companies.map((company) => (
                        <tr 
                          key={company.id} 
                          onClick={() => setSelectedEntity(company.id)}
                          className={`hover:bg-zinc-900/30 transition-colors group cursor-pointer relative ${selectedEntity === company.id ? 'bg-emerald-500/5' : ''}`}
                        >
                          <td className="px-6 py-4 relative">
                            {selectedEntity === company.id && <div className="absolute left-0 top-0 bottom-0 w-1 bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" />}
                            <span className="text-sm font-medium text-zinc-200">{company.name}</span>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-sm font-mono text-zinc-500">{company.id}</span>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-sm text-zinc-400">{company.manager}</span>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-1.5">
                              {company.systems.map(sys => (
                                <span key={sys} className="text-[10px] font-mono uppercase tracking-wider text-zinc-400 bg-zinc-900 px-1.5 py-0.5 rounded-[4px] border border-zinc-800">
                                  {sys}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="px-6 py-4 text-right">
                            <span className={`text-sm font-mono ${company.revenue === 'Unavailable' || viewState === 'partial' ? 'text-zinc-600' : 'text-zinc-300'}`}>
                              {viewState === 'partial' ? 'Unavailable' : company.revenue}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-center">
                            {company.health === 'good' ? (
                              <span className="inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-emerald-400">
                                <CheckCircle2 size={12} />
                                Active
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-amber-400">
                                <AlertCircle size={12} />
                                Warning
                              </span>
                            )}
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

        {/* Slide-over Side Panel */}
        <div 
          className={`absolute top-0 right-0 bottom-0 w-[420px] bg-[#0a0a0a] border-l border-zinc-800 shadow-2xl transform transition-transform duration-300 ease-in-out z-20 ${
            selectedEntity ? 'translate-x-0' : 'translate-x-full'
          }`}
        >
          {selectedEntity && (
            <CompanySidePanel 
              entityId={selectedEntity} 
              onClose={() => setSelectedEntity(null)} 
            />
          )}
        </div>
      </div>
    </div>
  );
}
