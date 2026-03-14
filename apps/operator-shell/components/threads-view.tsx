import { useState } from "react";
import { MessageSquare, Clock, Search, Loader2, AlertTriangle } from "lucide-react";
import { StateSwitcher, type ViewState } from "./state-switcher";

export function ThreadsView() {
  const [viewState, setViewState] = useState<ViewState>("success");

  const threads = [
    { id: "8f92a", title: "Tech Enterprise Active with Open Tickets", date: "Today, 10:42 AM", queries: 3 },
    { id: "b3c4d", title: "Churn Risk Q3 Analysis", date: "Yesterday, 14:15 PM", queries: 8 },
    { id: "e5f6g", title: "Recent Onboarding Teamleader Deals", date: "Mar 10, 09:30 AM", queries: 2 },
    { id: "h7i8j", title: "Upsell Candidates - High Revenue", date: "Mar 08, 16:45 PM", queries: 5 },
  ];

  return (
    <div className="flex-1 flex flex-col bg-[#050505] overflow-hidden">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-8 justify-between shrink-0 bg-zinc-950/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-[6px] bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
            <MessageSquare size={16} className="text-blue-400" />
          </div>
          <h1 className="text-lg font-medium text-zinc-100">Operator Threads</h1>
        </div>
        <div className="flex items-center gap-4">
          <StateSwitcher currentState={viewState} onStateChange={setViewState} />
          <button className="bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
            New Thread
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-4xl mx-auto flex flex-col gap-6">
          
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={16} />
            <input 
              type="text" 
              placeholder="Search past threads..." 
              className="w-full bg-zinc-900 border border-zinc-800 rounded-[8px] py-3 pl-10 pr-4 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-600 transition-all font-sans"
            />
          </div>

          {viewState === "loading" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500">
              <Loader2 size={24} className="animate-spin mb-4 text-blue-500" />
              <p className="text-sm font-medium">Loading threads...</p>
            </div>
          )}

          {viewState === "empty" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500 border border-dashed border-zinc-800 rounded-[8px] bg-zinc-900/20">
              <MessageSquare size={32} className="mb-4 text-zinc-600" />
              <p className="text-sm font-medium text-zinc-300">No threads found</p>
              <p className="text-xs mt-1 max-w-sm text-center">Start a new conversation with the Operator to explore your data.</p>
              <button className="mt-6 bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
                New Thread
              </button>
            </div>
          )}

          {viewState === "error" && (
            <div className="flex flex-col items-center justify-center py-24 text-zinc-500 border border-zinc-800 rounded-[8px] bg-rose-500/5">
              <AlertTriangle size={32} className="mb-4 text-rose-500" />
              <p className="text-sm font-medium text-rose-400">Failed to load threads</p>
              <p className="text-xs mt-1 max-w-sm text-center text-zinc-400">There was an error retrieving your conversation history. Please try again.</p>
              <button className="mt-6 bg-zinc-900 border border-zinc-700 hover:bg-zinc-800 text-zinc-300 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
                Retry
              </button>
            </div>
          )}

          {(viewState === "success" || viewState === "partial") && (
            <div className="flex flex-col gap-3">
              {viewState === "partial" && (
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-[6px] p-3 flex items-start gap-3 text-sm mb-2">
                  <AlertTriangle size={16} className="text-amber-500 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-amber-400 font-medium">Partial history loaded</p>
                    <p className="text-amber-500/70 mt-0.5">Some older threads could not be retrieved at this time.</p>
                  </div>
                </div>
              )}

              {threads.map(thread => (
                <div key={thread.id} className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-5 flex items-center justify-between hover:border-zinc-700 hover:bg-zinc-900/30 cursor-pointer transition-colors group">
                  <div className="flex flex-col gap-2">
                    <h3 className="text-base font-medium text-zinc-200 group-hover:text-blue-400 transition-colors">{thread.title}</h3>
                    <div className="flex items-center gap-4 text-xs font-mono text-zinc-500">
                      <span className="flex items-center gap-1.5"><Clock size={12} /> {thread.date}</span>
                      <span className="flex items-center gap-1.5"><MessageSquare size={12} /> {thread.queries} queries</span>
                      <span>ID: {thread.id}</span>
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
